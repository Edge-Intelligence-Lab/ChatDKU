"""
course_schedule.py

Tool factory for looking up course schedule data from the cleaned
class-data CSV produced by scripts/clean_classdata.py.
"""

import json
import re

import pandas as pd
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.core.utils import span_ctx_start
from chatdku.config import config


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Matches an optional separator (space, hyphen, or nothing) between the
# subject code and the catalog number, tolerating varied AI formatting.
_COURSE_RE = re.compile(r"^(?P<subject>[A-Za-z]+)[\s\-]*(?P<catalog>[A-Za-z0-9]+)$")


def _parse_course(raw: str) -> tuple[str, str]:
    """Parse a free-form course string into (SUBJECT, CATALOG).

    Handles deviations such as:
        "COMPSCI 101"   -> ("COMPSCI", "101")
        "COMPSCI101"    -> ("COMPSCI", "101")
        "COMPSCI-101"   -> ("COMPSCI", "101")
        "Chinese 101A"  -> ("CHINESE", "101A")

    Raises ValueError when the string cannot be parsed.
    """
    raw = raw.strip()
    m = _COURSE_RE.match(raw)
    if not m:
        raise ValueError(f"Cannot parse course code: '{raw}'")
    return m.group("subject").upper(), m.group("catalog").upper()


def _lookup(course_raw: str, df: pd.DataFrame) -> list[dict]:
    """Return all rows matching *course_raw* as a list of dicts."""
    subject, catalog = _parse_course(course_raw)

    mask = (df["Subject"].str.strip().str.upper() == subject) & (
        df["Catalog"].str.strip().str.upper() == catalog
    )

    matched = df.loc[mask]
    if matched.empty:
        return []
    return matched.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def CourseScheduleLookup(course_names: list[str]) -> str:
    """
    Look up the course schedule for one or more courses at Duke Kunshan University.

    Given a list of course codes (e.g. ["COMPSCI 101", "CHINESE 101A"]),
    returns the schedule information (sections, times, instructors, enrollment,
    etc.) for each course from the upcoming semester's class data.

    Handles formatting variations such as "COMPSCI101" or "COMPSCI-101".

    Args:
        course_names (list[str]): Courses to look up, e.g. ["STATS 202", "BIOL 305"].

    Returns:
        JSON string with schedule rows for every matched course,
        or an informative message when a course is not found.
    """
    classdata_csv_path = config.classdata_csv_path
    with span_ctx_start(
        "CourseScheduleLookup", OpenInferenceSpanKindValues.TOOL
    ) as span:
        span.set_attributes(
            {
                SpanAttributes.INPUT_VALUE: safe_json_dumps(
                    dict(course_names=course_names)
                ),
                SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
            }
        )

        try:
            df = pd.read_csv(classdata_csv_path)
        except FileNotFoundError:
            msg = f"Course schedule data file not found: {classdata_csv_path}"
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(error=msg)),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.ERROR), msg)
            raise FileNotFoundError(msg)

        try:
            results: dict[str, list[dict] | str] = {}
            for course in course_names:
                rows = _lookup(course, df)
                if rows:
                    results[course] = rows
                else:
                    results[course] = f"No schedule found for '{course}'."

            output = json.dumps(results, default=str)
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: output,
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
            return output

        except Exception as e:
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(error=str(e))
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.ERROR), str(e))
            raise


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from chatdku.setup import use_phoenix

    use_phoenix()
    import argparse

    parser = argparse.ArgumentParser(description="Test CourseScheduleLookup")
    parser.add_argument(
        "courses",
        nargs="+",
        help="Course codes to look up, e.g. 'COMPSCI 101' 'BIOL 305'",
    )
    args = parser.parse_args()

    __import__("pprint").pprint(CourseScheduleLookup(args.courses))
