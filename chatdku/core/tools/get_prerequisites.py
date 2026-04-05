import logging
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

logger = logging.getLogger(__name__)


def get_prereq(course: str, data_file_path: str) -> str:
    parts = re.sub(r" ", "_", course.strip()).strip().split(sep="_")
    course_subject = parts[0].upper()
    course_catalog = "".join(parts[1:])

    try:
        df = pd.read_csv(data_file_path, encoding="utf-16le")

        mask = (df.iloc[:, 2].astype(str).str.strip() == course_subject) & (
            df.iloc[:, 3].astype(str).str.strip() == course_catalog
        )

        if mask.any():
            matched = df.loc[mask].copy()
            matched["_eff_date"] = pd.to_datetime(
                matched.iloc[:, 1].astype(str).str.strip(), format="%m/%d/%Y"
            )
            latest = matched.sort_values("_eff_date", ascending=False).iloc[0]
            descr = latest.iloc[13]
            if pd.notna(descr) and descr.strip():
                return f"For {course_subject} {course_catalog}, {descr.strip()}\n(Source: DKUHub)"

        return f"No prerequisites found for {course_subject} {course_catalog}.\n(Source: DKUHub)"

    except FileNotFoundError:
        return "Prerequisites file not found."
    except Exception as e:
        logger.error("ERROR IN PREREQUISITE LOOKUP: %s", e)
        return f"Unknown error in finding prerequisite for {course}."


def PrerequisiteLookupOuter(prereq_csv_path: str):
    """
    DSPy tool factory for looking up course prerequisites.
    Returns a Phoenix-observable callable for the agent's tool list.

    Args:
        prereq_csv_path: Path to the prerequisites CSV file.
    """

    def PrerequisiteLookup(course_names: list[str]) -> str:
        """
        Look up the prerequisites for one or more courses at Duke Kunshan University.

        Given a list of course names (e.g. ["STATS 202", "COMPSCI 201", "MATH 206"]),
        returns the prerequisite and anti-requisite requirements for each course.
        Uses the latest available version of the course requirements.

        Good tool for answering questions about what courses are needed
        before taking specific courses.

        Args:
            course_names (list[str]): The courses to look up, e.g. ["STATS 202", "COMPSCI 101"].

        Returns:
            String describing the prerequisites for each course, separated by newlines.
        """
        with span_ctx_start(
            "PrerequisiteLookup", OpenInferenceSpanKindValues.TOOL
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
                results = [
                    get_prereq(course, prereq_csv_path) for course in course_names
                ]
                result = "\n".join(results)
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                            dict(result=result)
                        ),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
                span.set_status(Status(StatusCode.OK))
                return result
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

    return PrerequisiteLookup


if __name__ == "__main__":
    import os

    local_csv = os.path.join(
        os.path.dirname(__file__),
        "chatdku_external_data",
        "DK_SR_PREREQ_CRSE_CHATDKU.csv",
    )
    lookup = PrerequisiteLookupOuter(local_csv)
    print(lookup(["STATS 202", "COMPSCI 201"]))
