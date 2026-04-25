"""
course_recommender.py

Deterministic tool that combines major requirements, schedule availability,
and prerequisite data to produce a structured next-semester course recommendation
for a given student.

This replaces the need for 20+ individual executor tool-call iterations by doing
all the data-joining logic in Python, returning a single structured report.
"""

from __future__ import annotations

import itertools
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
from chatdku.config import config

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


def _load_prereq_df(prereq_csv_path: Path) -> pd.DataFrame:
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
    course_codes: list[str], classdata_csv_path: Path
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
# Schedule conflict detection
# ---------------------------------------------------------------------------

# Day codes used internally. Friday is included even though current data has
# no Friday meetings — the parser handles it if it ever appears.
_DAY_CODE_BY_COL = {"Mon": "M", "Tues": "Tu", "Wed": "W", "Thurs": "Th", "Fri": "F"}

# Time format observed in cleaned_classdata.csv: " 8:30:00.000000AM".
# Leading space and microseconds are normalized before parsing.
_TIME_RE = re.compile(
    r"^\s*(?P<h>\d{1,2}):(?P<m>\d{2})(?::\d{2}(?:\.\d+)?)?\s*(?P<ap>AM|PM)\s*$",
    re.IGNORECASE,
)

# A "primary" section is one whose label is purely numeric (e.g. "001", "003").
# Sections with letter suffixes ("001L", "001R", "009D") are labs / recitations
# / discussions that pair with a primary section. We only enumerate combinations
# of primary sections; secondaries are surfaced separately so the agent can
# tell the student "you also need to fit one of these."
_PRIMARY_SECTION_RE = re.compile(r"^\d+$")


def _parse_time_to_minutes(t: object) -> int | None:
    """Parse a string like ' 8:30:00.000000AM' to minutes since midnight.

    Returns None if the input is missing or unparseable. The CSV writer pads
    single-digit hours with a leading space; the regex tolerates that.
    """
    if t is None:
        return None
    s = str(t).strip()
    if not s or s.lower() == "nan":
        return None
    m = _TIME_RE.match(s)
    if not m:
        return None
    hour = int(m.group("h"))
    minute = int(m.group("m"))
    ap = m.group("ap").upper()
    if ap == "AM":
        if hour == 12:
            hour = 0
    else:  # PM
        if hour != 12:
            hour += 12
    return hour * 60 + minute


def _row_meeting_days(row: dict) -> set[str]:
    """Return the set of day codes ({'M','Tu','W','Th','F'}) this row meets."""
    days: set[str] = set()
    for col, code in _DAY_CODE_BY_COL.items():
        v = row.get(col)
        if v is not None and str(v).strip().upper() == "Y":
            days.add(code)
    return days


def _is_primary_section(section: object) -> bool:
    """True if section label is purely numeric (e.g. '001', '003')."""
    if section is None:
        return False
    return bool(_PRIMARY_SECTION_RE.match(str(section).strip()))


def _row_is_active(row: dict) -> bool:
    status = str(row.get("Class Status", "")).strip().lower()
    # Treat unknown / blank status as active so we don't silently drop rows.
    return status != "cancelled"


def _row_to_meeting(course: str, row: dict) -> dict | None:
    """Convert a CSV row to a structured meeting record.

    Returns None for rows that can't be scheduled (cancelled, no days, or
    unparseable times).
    """
    if not _row_is_active(row):
        return None
    days = _row_meeting_days(row)
    if not days:
        return None
    start = _parse_time_to_minutes(row.get("Mtg Start"))
    end = _parse_time_to_minutes(row.get("Mtg End"))
    if start is None or end is None or end <= start:
        return None
    section = str(row.get("Section", "")).strip()
    return {
        "course": course,
        "session": str(row.get("Session", "")).strip(),
        "section": section,
        "is_primary": _is_primary_section(section),
        "days": days,
        "start": start,
        "end": end,
        "instructor": str(row.get("Instructor", "")).strip(),
    }


def _meetings_conflict(a: dict, b: dict) -> bool:
    """Two meetings conflict iff same session, shared day, and time overlap."""
    if a["session"] != b["session"]:
        return False
    if not (a["days"] & b["days"]):
        return False
    return a["start"] < b["end"] and b["start"] < a["end"]


def _format_minutes(m: int) -> str:
    h, mm = divmod(m, 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mm:02d}{suffix}"


def _format_meeting(m: dict) -> str:
    days = "".join(d for d in ("M", "Tu", "W", "Th", "F") if d in m["days"])
    return f"§{m['section']} {days} {_format_minutes(m['start'])}-{_format_minutes(m['end'])}"


def _build_course_options(
    eligible_offered: list[tuple[str, list[dict]]],
) -> dict[str, dict[str, list[dict]]]:
    """Group eligible-and-offered courses into per-session, per-section meetings.

    Returns a nested dict:
        { course_code: { session_code: [meeting, meeting, ...] } }

    Each `meeting` belongs to exactly one section (primary or secondary).
    Cancelled / un-timed rows are dropped.
    """
    by_course: dict[str, dict[str, list[dict]]] = {}
    for course, rows in eligible_offered:
        for row in rows:
            meeting = _row_to_meeting(course, row)
            if meeting is None:
                continue
            by_course.setdefault(course, {}).setdefault(meeting["session"], []).append(
                meeting
            )
    return by_course


def _primary_meetings_by_course(
    course_options: dict[str, dict[str, list[dict]]],
    session: str,
) -> dict[str, list[dict]]:
    """For one session, return {course: [primary_meeting, ...]}.

    Courses with no primary section in this session are omitted (we can't
    enumerate them safely without knowing what to anchor on).
    """
    out: dict[str, list[dict]] = {}
    for course, by_session in course_options.items():
        meetings = by_session.get(session, [])
        primaries = [m for m in meetings if m["is_primary"]]
        if primaries:
            out[course] = primaries
    return out


def _secondary_meetings(
    course_options: dict[str, dict[str, list[dict]]],
    course: str,
    session: str,
) -> list[dict]:
    return [
        m
        for m in course_options.get(course, {}).get(session, [])
        if not m["is_primary"]
    ]


def _enumerate_session_schedules(
    primaries_by_course: dict[str, list[dict]],
    priority_index: dict[str, int],
    target_size: int,
    max_results: int,
) -> list[list[dict]]:
    """Return up to `max_results` non-conflicting combinations of `target_size`
    distinct courses (one primary section each), ranked by priority.

    Ranking: lower sum of priority_index across the chosen courses wins
    (priority_index reflects ordering in the requirements doc — earlier-listed
    items are higher priority).
    """
    courses = list(primaries_by_course.keys())
    if len(courses) < target_size:
        return []

    # Sort courses by priority so combinations are generated roughly best-first.
    courses.sort(key=lambda c: priority_index.get(c, 10_000))

    results: list[tuple[int, list[dict]]] = []
    for combo_courses in itertools.combinations(courses, target_size):
        # For each course, try each primary-section choice; emit the first
        # non-conflicting assignment found. We keep things small by cartesian-
        # producting only over primaries (typically 1-3 per course).
        section_lists = [primaries_by_course[c] for c in combo_courses]
        for assignment in itertools.product(*section_lists):
            ok = True
            for i in range(len(assignment)):
                for j in range(i + 1, len(assignment)):
                    if _meetings_conflict(assignment[i], assignment[j]):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                score = sum(priority_index.get(c, 10_000) for c in combo_courses)
                results.append((score, list(assignment)))
                break  # one valid assignment per course-combo is enough

    results.sort(key=lambda r: r[0])
    return [meetings for _, meetings in results[:max_results]]


def _format_schedule_block(
    schedule: list[dict],
    course_options: dict[str, dict[str, list[dict]]],
    session: str,
) -> str:
    """Render a single schedule combination as a Markdown block."""
    lines = []
    for meeting in schedule:
        course = meeting["course"]
        instr = f" — {meeting['instructor']}" if meeting["instructor"] else ""
        lines.append(f"  - **{course}** {_format_meeting(meeting)}{instr}")
        secondaries = _secondary_meetings(course_options, course, session)
        if secondaries:
            sec_strs = [_format_meeting(s) for s in secondaries]
            lines.append(
                f"    - *also requires one of (verify fit):* {' | '.join(sec_strs)}"
            )
    return "\n".join(lines)


def _build_schedules_section(
    eligible_offered: list[tuple[str, list[dict]]],
    priority_order: list[str],
    target_sizes: tuple[int, ...] = (3, 2),
    max_per_session_per_size: int = 3,
) -> str:
    """Build the Markdown section listing plausible non-conflicting schedules
    per session. Returns an empty string if no schedules can be built.
    """
    course_options = _build_course_options(eligible_offered)
    if not course_options:
        return ""

    priority_index = {c: i for i, c in enumerate(priority_order)}

    # Discover sessions present in the data, in stable order.
    sessions: list[str] = []
    for by_session in course_options.values():
        for s in by_session.keys():
            if s and s not in sessions:
                sessions.append(s)
    sessions.sort()  # 7W1 before 7W2 alphabetically — matches calendar order

    if not sessions:
        return ""

    out = ["### Plausible non-conflicting schedules (per 7-week session)\n"]
    out.append(
        "*Each option below is a set of primary lecture sections that share no "
        "meeting time. Lab/recitation/discussion sections are listed separately "
        "and must also be fitted in by the student.*\n"
    )
    any_emitted = False
    for session in sessions:
        primaries = _primary_meetings_by_course(course_options, session)
        out.append(f"#### Session {session}")
        if not primaries:
            out.append("- *(no primary sections with parsable meeting times)*\n")
            continue
        emitted_for_session = False
        for size in target_sizes:
            schedules = _enumerate_session_schedules(
                primaries,
                priority_index,
                target_size=size,
                max_results=max_per_session_per_size,
            )
            if not schedules:
                continue
            out.append(f"**{size}-course options:**")
            for idx, sched in enumerate(schedules, 1):
                out.append(f"- Option {idx}:")
                out.append(_format_schedule_block(sched, course_options, session))
            out.append("")
            emitted_for_session = True
            any_emitted = True
        if not emitted_for_session:
            out.append(
                "- *(could not assemble a non-conflicting combination from "
                "the eligible pool)*\n"
            )

    if not any_emitted:
        return ""
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def BuildSemesterPlan(
    major: str,
    completed_courses: list[str],
) -> str:
    """
    Build a next-semester course plan for a DKU student: figures out what
    requirements are still outstanding, which of those courses are actually
    being offered, which the student is prerequisite-eligible for, and
    enumerates concrete non-conflicting schedule combinations.

    Use this whenever a student asks "what should I take", "help me plan my
    schedule", "build me a semester", "am I on track to graduate", or any
    other planning / multi-course recommendation question. Prefer this over
    calling MajorRequirementsLookup + CourseScheduleLookup + PrerequisiteLookup
    separately — this tool already joins all three and adds time-conflict
    detection on top.

    Given the student's major and the courses they have already completed,
    this tool:
      1. Looks up the graduation requirements for the student's major.
      2. Looks up the university-wide common-core requirements.
      3. Identifies which required courses still need to be completed.
      4. Checks which remaining courses are offered next semester.
      5. Checks whether the student meets prerequisites for each available course.
      6. Enumerates 2- and 3-course combinations per 7-week session whose
         primary lecture sections share no overlapping meeting time.
      7. Returns a grouped Markdown report: recommended, eligible-but-not-
         offered, prerequisites-not-met, no-schedule-data, plus the per-
         session list of plausible non-conflicting schedules.

    Args:
        major (str): The student's major and optional track, e.g. "data science"
                     or "computation and design computer science".
        completed_courses (list[str]): Courses the student has already completed
            or is currently taking, e.g. ["COMPSCI 101", "MATH 105", "STATS 201"].
            Pass an empty list for incoming students with no prior coursework.

    Returns:
        A Markdown-formatted recommendation report including conflict-free
        schedule combinations.
    """
    req_dir = Path(config.major_req_dir)
    classdata_csv_path = Path(config.classdata_csv_path)
    prereq_csv_path = Path(config.prereq_csv_path)
    with span_ctx_start("BuildSemesterPlan", OpenInferenceSpanKindValues.TOOL) as span:
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
            raise e


# ---------------------------------------------------------------------------
# Core recommendation logic
# ---------------------------------------------------------------------------


def _run_recommendation(
    major: str,
    completed_courses: list[str],
    req_dir: Path,
    classdata_csv_path: Path,
    prereq_csv_path: Path,
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

    # eligible_and_offered keeps both the display summary and the raw rows so
    # the schedule builder downstream has structured access to meeting times.
    eligible_and_offered: list[tuple[str, str, list[dict]]] = []
    eligible_not_offered: list[str] = []
    not_eligible: list[tuple[str, str]] = []  # (course, reason)
    no_schedule_data: list[str] = []

    for course in remaining:
        if course in offered:
            if prereq_available:
                met, reason = prerequisites_met(course, completed_set, prereq_df)
                if met:
                    schedule_summary = _format_schedule_rows(offered[course])
                    eligible_and_offered.append(
                        (course, schedule_summary, offered[course])
                    )
                else:
                    not_eligible.append((course, reason))
            else:
                schedule_summary = _format_schedule_rows(offered[course])
                eligible_and_offered.append(
                    (course, schedule_summary, offered[course])
                )
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
        for course, schedule, _rows in eligible_and_offered:
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

    # Schedule enumeration: prove which 2-/3-course combinations have no
    # primary-section time conflicts. Priority order is the order courses
    # appear in the requirements doc (major then common-core).
    eligible_pairs = [(c, rows) for c, _summary, rows in eligible_and_offered]
    schedules_md = _build_schedules_section(
        eligible_offered=eligible_pairs,
        priority_order=all_required,
    )
    if schedules_md:
        lines.append(schedules_md)
        lines.append("")

    lines.append("---")
    lines.append(
        "*Note: Prerequisites are checked using DKUHub data. "
        "Complex or conditional prerequisites (e.g. instructor consent, GPA requirements) "
        "may not be captured — always confirm with your academic advisor. "
        "Schedule conflict checks cover only primary lecture sections; verify "
        "lab/recitation/discussion fit before registering.*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    from chatdku.setup import use_phoenix

    use_phoenix()

    parser = argparse.ArgumentParser(description="Test BuildSemesterPlan")
    parser.add_argument("--major", required=True, help="Student's major")
    parser.add_argument(
        "--completed",
        nargs="*",
        default=[],
        help="Completed course codes, e.g. COMPSCI 101 MATH 105",
    )
    args = parser.parse_args()

    __import__("pprint").pprint(
        BuildSemesterPlan(major=args.major, completed_courses=args.completed)
    )
