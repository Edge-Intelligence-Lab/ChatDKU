"""
course_recommender.py

Deterministic tool that combines major requirements, schedule availability,
and prerequisite data to produce a structured next-semester course recommendation
for a given student.

This replaces the need for 20+ individual executor tool-call iterations by doing
all the data-joining logic in Python, returning a single structured report.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.core.tools.major_requirements import _best_match, _list_stems
from chatdku.core.utils import span_ctx_start

# ---------------------------------------------------------------------------
# Course code parsing
# ---------------------------------------------------------------------------

# Matches DKU course codes like COMPSCI 201, STATS 202A, MATH 105.
# Handles subject codes of 2-10 uppercase letters followed by a 3-digit
# catalog number with an optional trailing letter (e.g. 101A).
_COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,10})\s+(\d{3}[A-Z]?)\b")

# Known DKU subject codes — used to filter false positives from the markdown.
_KNOWN_SUBJECTS = {
    "DKU",
    "GERMAN",
    "INDSTU",
    "JAPANESE",
    "KOREAN",
    "MUSIC",
    "SPANISH",
    "ARHU",
    "ARTS",
    "BEHAVSCI",
    "BIOL",
    "CHEM",
    "CHINESE",
    "COMPDSGN",
    "COMPSCI",
    "CULANTH",
    "CULMOVE",
    "CULSOC",
    "EAP",
    "ECON",
    "ENVIR",
    "ETHLDR",
    "GCHINA",
    "GCULS",
    "GLHLTH",
    "GLOCHALL",
    "HIST",
    "HUM",
    "INFOSCI",
    "INSTGOV",
    "LIT",
    "MATH",
    "MATSCI",
    "MEDIA",
    "MEDIART",
    "NEUROSCI",
    "PHIL",
    "PHYS",
    "PHYSEDU",
    "POLECON",
    "POLSCI",
    "PPE",
    "PSYCH",
    "PUBPOL",
    "SOCIOL",
    "SOSC",
    "STATS",
    "USTUD",
    "WOC",
    "RELIG",
    "MINITERM",
}


def parse_course_codes(md_text: str) -> list[str]:
    """Extract all DKU course codes from a Markdown requirements document.

    Returns a deduplicated list of strings like ["COMPSCI 201", "STATS 202"].
    Only returns codes whose subject prefix is a known DKU subject code, to
    filter out false positives (e.g. headings that accidentally match the regex).
    """
    found = []
    for subject, catalog in _COURSE_CODE_RE.findall(md_text):
        if subject in _KNOWN_SUBJECTS:
            found.append(f"{subject} {catalog}")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    result = []
    for code in found:
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


# ---------------------------------------------------------------------------
# Prerequisite satisfaction
# ---------------------------------------------------------------------------


def _load_prereq_df(prereq_csv_path: str) -> pd.DataFrame:
    return pd.read_csv(prereq_csv_path, encoding="utf-16le")


def _get_prereq_text(course: str, prereq_df: pd.DataFrame) -> str | None:
    """Return the raw prerequisite description for *course*, or None if absent."""
    parts = re.sub(r"[\s\-]", "_", course.strip()).split("_")
    subject = parts[0].upper()
    catalog = "".join(parts[1:])

    mask = (prereq_df.iloc[:, 2].astype(str).str.strip() == subject) & (
        prereq_df.iloc[:, 3].astype(str).str.strip() == catalog
    )
    if not mask.any():
        return None

    matched = prereq_df.loc[mask].copy()
    matched["_eff_date"] = pd.to_datetime(
        matched.iloc[:, 1].astype(str).str.strip(), format="%m/%d/%Y", errors="coerce"
    )
    latest = matched.sort_values("_eff_date", ascending=False).iloc[0]
    descr = latest.iloc[13]
    if pd.notna(descr) and str(descr).strip():
        return str(descr).strip()
    return None


def prerequisites_met(
    course: str,
    completed_set: set[str],
    prereq_df: pd.DataFrame,
) -> tuple[bool, str]:
    """Check whether a student's completed courses satisfy *course*'s prerequisites.

    Returns:
        (True, "")                        — no prerequisites or all satisfied
        (False, "<reason / raw text>")    — prerequisites not met
        (True, "<warning>")               — best-effort: possible OR-path satisfied

    Strategy (best-effort on free-form text):
    1. Extract all course codes mentioned in the prereq text.
    2. If the text contains "or": eligible if ANY mentioned code is completed.
    3. Otherwise (AND / simple): eligible if ALL mentioned codes are completed.
    4. If no codes are found in the prereq text, assume no structured prerequisite
       and return eligible (the raw text is included for the Synthesizer).
    """
    text = _get_prereq_text(course, prereq_df)
    if text is None:
        return True, ""

    # Strip anti-requisite section so its course codes aren't treated as prerequisites.
    prereq_text = re.split(r"[Aa]nti[\s\-]?[Rr]equisite", text)[0].strip()

    # Extract all course codes mentioned in the prerequisite portion only.
    codes_in_prereq = [
        f"{s} {c}"
        for s, c in _COURSE_CODE_RE.findall(prereq_text)
        if s in _KNOWN_SUBJECTS
    ]

    if not codes_in_prereq:
        # No structured codes — can't verify; pass through with a note.
        return True, f"(Unstructured prerequisite — verify manually: {text})"

    has_or = " or " in prereq_text.lower()

    if has_or:
        satisfied = any(c in completed_set for c in codes_in_prereq)
        if satisfied:
            return True, ""
        missing = [c for c in codes_in_prereq if c not in completed_set]
        return (
            False,
            f"Requires one of: {', '.join(codes_in_prereq)} (missing: {', '.join(missing)})",
        )
    else:
        missing = [c for c in codes_in_prereq if c not in completed_set]
        if not missing:
            return True, ""
        return (
            False,
            f"Requires: {', '.join(codes_in_prereq)} (missing: {', '.join(missing)})",
        )


# ---------------------------------------------------------------------------
# Schedule lookup (batch)
# ---------------------------------------------------------------------------


def _get_offered_courses(
    course_codes: list[str], classdata_csv_path: str
) -> dict[str, list[dict]]:
    """Return a mapping of course_code → list of schedule rows for offered courses.

    Courses not found in the schedule CSV are omitted from the result.
    """
    try:
        df = pd.read_csv(classdata_csv_path)
    except FileNotFoundError:
        return {}

    result: dict[str, list[dict]] = {}
    for code in course_codes:
        # Parse subject and catalog from code like "COMPSCI 201"
        parts = code.strip().split()
        if len(parts) != 2:
            continue
        subject, catalog = parts[0].upper(), parts[1].upper()
        mask = (df["Subject"].astype(str).str.strip().str.upper() == subject) & (
            df["Catalog"].astype(str).str.strip().str.upper() == catalog
        )
        rows = df.loc[mask].to_dict(orient="records")
        if rows:
            result[code] = rows
    return result


_DAY_COLS = [("Mon", "M"), ("Tues", "Tu"), ("Wed", "W"), ("Thurs", "Th"), ("Fri", "F")]


def _format_schedule_rows(rows: list[dict]) -> str:
    """Produce a compact, human-readable schedule summary for a course.

    Handles the real cleaned_classdata.csv column layout:
    - Day columns: Mon / Tues / Wed / Thurs / Fri (value "Y" or "N")
    - Time columns: Mtg Start / Mtg End
    """
    # Deduplicate by section to avoid listing lab/recitation rows as separate entries.
    seen_sections: set[str] = set()
    parts = []
    for row in rows:
        section = str(row.get("Section", "")).strip()
        if section in seen_sections:
            continue
        seen_sections.add(section)

        session = str(row.get("Session", "")).strip()
        start = str(row.get("Mtg Start", "")).strip().rstrip("0").rstrip(":")
        end = str(row.get("Mtg End", "")).strip().rstrip("0").rstrip(":")
        instructor = str(row.get("Instructor", "")).strip()
        status = str(row.get("Class Status", "")).strip()

        # Build day string from individual boolean columns.
        days = "".join(
            abbr
            for col, abbr in _DAY_COLS
            if str(row.get(col, "N")).strip().upper() == "Y"
        )

        line_parts = []
        if section:
            line_parts.append(f"§{section}")
        if session:
            line_parts.append(f"({session})")
        if days:
            time_str = f"{start}–{end}" if start and end else (start or end)
            line_parts.append(f"{days} {time_str}" if time_str else days)
        if instructor:
            line_parts.append(f"Instr: {instructor}")
        if status and status.lower() != "active":
            line_parts.append(f"[{status}]")
        parts.append(", ".join(line_parts))
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def CourseRecommenderOuter(
    requirements_dir: str,
    classdata_csv_path: str,
    prereq_csv_path: str,
):
    """
    DSPy tool factory for generating a structured next-semester course recommendation.

    Combines major requirements data, schedule availability, and prerequisite
    satisfaction into a single structured report, so the Executor only needs
    one tool call to get a complete recommendation.

    Args:
        requirements_dir: Directory containing per-major Markdown requirement files.
        classdata_csv_path: Path to the cleaned class-schedule CSV.
        prereq_csv_path: Path to the prerequisites CSV (UTF-16LE encoded).
    """
    req_dir = Path(requirements_dir)

    def CourseRecommender(
        major: str,
        completed_courses: list[str],
    ) -> str:
        """
        Generate a structured next-semester course recommendation for a DKU student.

        Given the student's major and the courses they have already completed,
        this tool:
          1. Looks up the graduation requirements for the student's major.
          2. Looks up the university-wide common-core requirements.
          3. Identifies which required courses still need to be completed.
          4. Checks which remaining courses are offered next semester.
          5. Checks whether the student meets prerequisites for each available course.
          6. Returns a grouped report: recommended, eligible-but-not-offered,
             prerequisites-not-met, and no-schedule-data categories.

        Args:
            major (str): The student's major and optional track, e.g. "data science"
                         or "computation and design computer science".
            completed_courses (list[str]): Courses the student has already completed
                or is currently taking, e.g. ["COMPSCI 101", "MATH 105", "STATS 201"].

        Returns:
            A Markdown-formatted recommendation report.
        """
        with span_ctx_start(
            "CourseRecommender", OpenInferenceSpanKindValues.TOOL
        ) as span:
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        {
                            "major": major,
                            "completed_courses": completed_courses,
                        }
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            try:
                result = _run_recommendation(
                    major=major,
                    completed_courses=completed_courses,
                    req_dir=req_dir,
                    classdata_csv_path=classdata_csv_path,
                    prereq_csv_path=prereq_csv_path,
                )
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: result[:500],
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.TEXT.value,
                    }
                )
                span.set_status(Status(StatusCode.OK))
                return result

            except Exception as e:
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps({"error": str(e)}),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
                span.set_status(Status(StatusCode.ERROR), str(e))
                raise

    return CourseRecommender


# ---------------------------------------------------------------------------
# Core recommendation logic
# ---------------------------------------------------------------------------


def _run_recommendation(
    major: str,
    completed_courses: list[str],
    req_dir: Path,
    classdata_csv_path: str,
    prereq_csv_path: str,
) -> str:
    if not req_dir.is_dir():
        raise FileNotFoundError(f"Requirements directory not found: {req_dir}")

    stems = _list_stems(req_dir)

    # --- 1. Load major requirements ---
    matched_major = _best_match(major, stems)
    if matched_major is None:
        return (
            f"No matching major found for '{major}'. "
            "Please check the major name and try again."
        )
    major_md = (req_dir / f"{matched_major}.md").read_text(encoding="utf-8")
    major_courses = parse_course_codes(major_md)

    # --- 2. Load common-core requirements ---
    common_core_md = ""
    common_core_stem = _best_match("requirements for all majors", stems)
    common_core_courses: list[str] = []
    if common_core_stem:
        common_core_md = (req_dir / f"{common_core_stem}.md").read_text(
            encoding="utf-8"
        )
        common_core_courses = parse_course_codes(common_core_md)

    # --- 3. Compute remaining required courses ---
    completed_set = {c.strip().upper() for c in completed_courses}
    # Normalize completed_courses to "SUBJECT NNN" format for comparison.
    # Users might type "CS 101" or "compsci 101" — handle by uppercasing.
    all_required = list(
        dict.fromkeys(major_courses + common_core_courses)
    )  # preserve order, deduplicate
    remaining = [c for c in all_required if c.upper() not in completed_set]

    if not remaining:
        return (
            f"## Course Recommendation for {matched_major}\n\n"
            "You have completed all required courses for this major. "
            "Consider taking electives or checking with your advisor about graduation requirements."
        )

    # --- 4. Check schedule availability ---
    offered = _get_offered_courses(remaining, classdata_csv_path)

    # --- 5. Check prerequisites for offered courses ---
    try:
        prereq_df = _load_prereq_df(prereq_csv_path)
        prereq_available = True
    except Exception:
        prereq_df = None
        prereq_available = False

    eligible_and_offered: list[tuple[str, str]] = []  # (course, schedule_summary)
    eligible_not_offered: list[str] = []
    not_eligible: list[tuple[str, str]] = []  # (course, reason)
    no_schedule_data: list[str] = []

    for course in remaining:
        if course in offered:
            if prereq_available:
                met, reason = prerequisites_met(course, completed_set, prereq_df)
                if met:
                    schedule_summary = _format_schedule_rows(offered[course])
                    eligible_and_offered.append((course, schedule_summary))
                else:
                    not_eligible.append((course, reason))
            else:
                schedule_summary = _format_schedule_rows(offered[course])
                eligible_and_offered.append((course, schedule_summary))
        else:
            if prereq_available:
                met, reason = prerequisites_met(course, completed_set, prereq_df)
                if met:
                    eligible_not_offered.append(course)
                else:
                    not_eligible.append((course, reason))
            else:
                # No schedule and no prereq data — just report as not offered.
                no_schedule_data.append(course)

    # --- 6. Build report ---
    lines = [f"## Course Recommendation for {matched_major}\n"]
    lines.append(f"**Matched requirements file:** `{matched_major}.md`")
    lines.append(f"**Total required courses:** {len(all_required)}")
    lines.append(f"**Completed:** {len(all_required) - len(remaining)}")
    lines.append(f"**Remaining:** {len(remaining)}\n")

    lines.append("### Recommended — eligible and offered next semester")
    if eligible_and_offered:
        for course, schedule in eligible_and_offered:
            lines.append(f"- **{course}** — {schedule}")
    else:
        lines.append("- *(none)*")
    lines.append("")

    lines.append("### Eligible but not offered next semester")
    if eligible_not_offered:
        for course in eligible_not_offered:
            lines.append(f"- {course}")
    else:
        lines.append("- *(none)*")
    lines.append("")

    lines.append("### Not eligible — prerequisites not yet met")
    if not_eligible:
        for course, reason in not_eligible:
            lines.append(f"- **{course}**: {reason}")
    else:
        lines.append("- *(none)*")
    lines.append("")

    if no_schedule_data:
        lines.append("### Required courses with no schedule data")
        for course in no_schedule_data:
            lines.append(f"- {course}")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Note: Prerequisites are checked using DKUHub data. "
        "Complex or conditional prerequisites (e.g. instructor consent, GPA requirements) "
        "may not be captured — always confirm with your academic advisor.*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    from chatdku.setup import use_phoenix

    use_phoenix()

    parser = argparse.ArgumentParser(description="Test CourseRecommender")
    parser.add_argument(
        "--requirements-dir",
        default="/datapool/chatdku_external_data/doc_testing/output/ug_bulletin_2023-2024",
    )
    parser.add_argument(
        "--classdata-csv",
        default="/datapool/chatdku_external_data/cleaned_classdata.csv",
    )
    parser.add_argument(
        "--prereq-csv",
        default="/datapool/chatdku_external_data/DK_SR_PREREQ_CRSE_CHATDKU.csv",
    )
    parser.add_argument("--major", required=True, help="Student's major")
    parser.add_argument(
        "--completed",
        nargs="*",
        default=[],
        help="Completed course codes, e.g. COMPSCI 101 MATH 105",
    )
    args = parser.parse_args()

    recommender = CourseRecommenderOuter(
        requirements_dir=args.requirements_dir,
        classdata_csv_path=args.classdata_csv,
        prereq_csv_path=args.prereq_csv,
    )
    print(recommender(major=args.major, completed_courses=args.completed))
