"""End-to-end smoke test for CourseRecommender's schedule enumeration.

For each student profile:
  1. Run CourseRecommender.
  2. Parse the "Plausible non-conflicting schedules" section out of the report.
  3. Re-look-up each cited section in cleaned_classdata.csv and recompute
     conflicts independently — fail loudly if the tool ever recommends a
     schedule whose primary sections actually clash on day+time.

Run via: ./devsync.sh scripts/smoke_course_recommender.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

import pandas as pd

from chatdku.config import config
from chatdku.core.tools.course_recommender import (
    CourseRecommender,
    _parse_time_to_minutes,
    _row_meeting_days,
)


@dataclass
class CitedMeeting:
    course: str
    section: str
    days_str: str
    start_str: str
    end_str: str


# Matches lines like:  - **COMPSCI 201** §001 MW 12:00PM-2:30PM — Instr Name
_LINE_RE = re.compile(
    r"^\s*-\s+\*\*([A-Z]+ \d+[A-Z]?)\*\*\s+§(\S+)\s+([MTuWThF]+)\s+"
    r"([\d:]+[AP]M)-([\d:]+[AP]M)"
)

# Section header inside an option group:  - Option N:
_OPTION_RE = re.compile(r"^\s*-\s+Option\s+\d+:")
_SESSION_HEADER_RE = re.compile(r"^####\s+Session\s+(\S+)")


@dataclass
class Schedule:
    session: str
    option_idx: int
    meetings: list[CitedMeeting]


def parse_schedules(report: str) -> list[Schedule]:
    """Extract every (session, option, [meetings]) tuple from the report."""
    schedules: list[Schedule] = []
    current_session = ""
    current: Schedule | None = None
    option_counter = 0
    for line in report.splitlines():
        sess_m = _SESSION_HEADER_RE.match(line)
        if sess_m:
            current_session = sess_m.group(1)
            option_counter = 0
            if current is not None:
                schedules.append(current)
                current = None
            continue
        if _OPTION_RE.match(line):
            if current is not None:
                schedules.append(current)
            option_counter += 1
            current = Schedule(
                session=current_session,
                option_idx=option_counter,
                meetings=[],
            )
            continue
        m = _LINE_RE.match(line)
        if m and current is not None:
            current.meetings.append(
                CitedMeeting(
                    course=m.group(1),
                    section=m.group(2),
                    days_str=m.group(3),
                    start_str=m.group(4),
                    end_str=m.group(5),
                )
            )
    if current is not None:
        schedules.append(current)
    return schedules


def _split_days(s: str) -> set[str]:
    out: set[str] = set()
    i = 0
    tokens = ("Th", "Tu", "M", "W", "F")  # longest-first to avoid Th->T+h misread
    while i < len(s):
        matched = None
        for t in tokens:
            if s[i:].startswith(t):
                matched = t
                break
        if matched is None:
            i += 1
            continue
        out.add(matched)
        i += len(matched)
    return out


def _parse_label_time(s: str) -> int | None:
    """Parse times that the report emits, e.g. '12:00PM' or '2:30PM'."""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})(AM|PM)\s*$", s, re.IGNORECASE)
    if not m:
        return None
    h = int(m.group(1))
    mm = int(m.group(2))
    ap = m.group(3).upper()
    if ap == "AM":
        if h == 12:
            h = 0
    else:
        if h != 12:
            h += 12
    return h * 60 + mm


def verify_against_csv(schedules: list[Schedule], df: pd.DataFrame) -> list[str]:
    """For each schedule, look up each meeting in the CSV and check internal
    consistency + pairwise non-overlap. Returns a list of human-readable
    violations (empty if all schedules are valid)."""
    errors: list[str] = []

    for sched in schedules:
        # Resolve each cited section against the CSV ground truth.
        resolved: list[dict] = []
        for cm in sched.meetings:
            subject, catalog = cm.course.split()
            mask = (
                (df["Subject"].astype(str).str.strip().str.upper() == subject)
                & (df["Catalog"].astype(str).str.strip().str.upper() == catalog)
                & (df["Section"].astype(str).str.strip() == cm.section)
                & (df["Session"].astype(str).str.strip() == sched.session)
            )
            rows = df[mask]
            if len(rows) == 0:
                errors.append(
                    f"[{sched.session} opt{sched.option_idx}] "
                    f"cited section not in CSV: {cm.course} §{cm.section}"
                )
                continue
            row = rows.iloc[0].to_dict()
            csv_days = _row_meeting_days(row)
            csv_start = _parse_time_to_minutes(row.get("Mtg Start"))
            csv_end = _parse_time_to_minutes(row.get("Mtg End"))

            # Cross-check the report's day/time string matches the CSV row.
            report_days = _split_days(cm.days_str)
            report_start = _parse_label_time(cm.start_str)
            report_end = _parse_label_time(cm.end_str)
            if csv_days != report_days:
                errors.append(
                    f"[{sched.session} opt{sched.option_idx}] day mismatch for "
                    f"{cm.course} §{cm.section}: report {sorted(report_days)} vs "
                    f"csv {sorted(csv_days)}"
                )
            if csv_start != report_start or csv_end != report_end:
                errors.append(
                    f"[{sched.session} opt{sched.option_idx}] time mismatch for "
                    f"{cm.course} §{cm.section}: report {report_start}-{report_end} "
                    f"vs csv {csv_start}-{csv_end}"
                )

            resolved.append(
                {
                    "course": cm.course,
                    "section": cm.section,
                    "days": csv_days,
                    "start": csv_start,
                    "end": csv_end,
                }
            )

        # Pairwise conflict check on the CSV-grounded values.
        for i in range(len(resolved)):
            for j in range(i + 1, len(resolved)):
                a, b = resolved[i], resolved[j]
                if a["start"] is None or b["start"] is None:
                    continue
                if not (a["days"] & b["days"]):
                    continue
                if a["start"] < b["end"] and b["start"] < a["end"]:
                    errors.append(
                        f"[{sched.session} opt{sched.option_idx}] CONFLICT: "
                        f"{a['course']} §{a['section']} ({sorted(a['days'])} "
                        f"{a['start']}-{a['end']}) overlaps "
                        f"{b['course']} §{b['section']} ({sorted(b['days'])} "
                        f"{b['start']}-{b['end']})"
                    )

    return errors


# --- Test profiles ---------------------------------------------------------

PROFILES = [
    # (name, major, completed)
    ("CS sophomore — basics done", "computer science", ["COMPSCI 101", "MATH 105"]),
    ("CS senior — most major done", "computer science",
     ["COMPSCI 101", "COMPSCI 201", "COMPSCI 203", "COMPSCI 205", "COMPSCI 301",
      "COMPSCI 308", "MATH 105", "MATH 201", "STATS 201"]),
    ("Data science sophomore", "data science",
     ["MATH 105", "STATS 101", "COMPSCI 101"]),
    ("Applied math fresh start", "applied mathematics and computational sciences", []),
    ("Global health new student", "global health", []),
    ("Empty completions, undeclared-ish", "behavioral science", []),
]


def run_one(name: str, major: str, completed: list[str], df: pd.DataFrame) -> int:
    print(f"\n{'=' * 76}")
    print(f"PROFILE: {name}")
    print(f"  major={major!r}, completed={completed}")
    print(f"{'-' * 76}")
    try:
        report = CourseRecommender(major=major, completed_courses=completed)
    except Exception as e:
        print(f"  !! CourseRecommender threw: {e!r}")
        return 1

    # Print the schedules section only (keep output digestible).
    if "### Plausible non-conflicting schedules" in report:
        section = report[report.index("### Plausible non-conflicting schedules"):]
        # Cut at the trailing footer if present.
        if "\n---" in section:
            section = section[: section.index("\n---")]
        print(section)
    else:
        print("  (no schedules section emitted)")

    schedules = parse_schedules(report)
    print(f"\n  parsed {len(schedules)} option(s) from report")

    errors = verify_against_csv(schedules, df)
    if errors:
        print(f"  !! {len(errors)} VIOLATION(S):")
        for e in errors:
            print(f"     - {e}")
        return 1
    print("  OK — every cited schedule is conflict-free per CSV ground truth")
    return 0


def main() -> int:
    from chatdku.setup import use_phoenix

    use_phoenix()
    df = pd.read_csv(config.classdata_csv_path)
    failures = 0
    for name, major, completed in PROFILES:
        failures += run_one(name, major, completed, df)
    print(f"\n{'=' * 76}")
    if failures:
        print(f"FAIL: {failures} profile(s) had violations")
        return 1
    print("PASS: all profiles produced conflict-free schedules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
