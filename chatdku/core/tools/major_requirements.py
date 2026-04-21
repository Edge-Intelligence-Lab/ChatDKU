#!/usr/bin/env python3
"""
major_requirements.py

Tool factory for looking up DKU major/track graduation requirements.
Requirements are stored as Markdown files (one per major/track combination)
parsed from the UG Bulletin.

Directory layout expected:
    <requirements_dir>/
        data-science.md
        computation-and-design-computer-science.md
        behavioral-science-psychology.md
        requirements-for-all-majors.md
        ...

File stems use lower-kebab-case with the major name followed by the track
name when applicable, e.g. "global-health-biology".
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode
from thefuzz import fuzz, process

from chatdku.core.utils import span_ctx_start
from chatdku.config import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_stem_dict(stems: list[str]) -> dict[str, str]:
    """Build a dictionary of stems to their normalized versions.
    For example: {"data-science": "data science"}
    """

    def _replace_hyphens(stem: str) -> str:
        return [stem.replace("-", " ")]

    stem_dict = {}
    for stem in stems:
        stem_dict[stem] = _replace_hyphens(stem)
    return stem_dict


def _clean_query(query: str) -> str:
    query = query.lower()
    query = re.sub(r"[/\\&,\-]", " ", query)
    query = re.sub(r"[^a-z0-9 ]", "", query)
    return query


_MIN_MATCH_SCORE = 40  # below this, treat as no match


def _best_match(query: str, stems: list[str]) -> str | None:
    """
    Return the filename stem that best matches *query* by token-set ratio.
    Returns None when the best score is below _MIN_MATCH_SCORE.
    """
    stems_dict = _build_stem_dict(stems)
    query = _clean_query(query)

    matches = process.extract(
        query,
        stems_dict,
        scorer=fuzz.token_set_ratio,
        limit=1,
    )

    if not matches:
        return None
    score, key = matches[0][1], matches[0][2]
    return key if score >= _MIN_MATCH_SCORE else None


def _list_stems(requirements_dir: Path) -> list[str]:
    return sorted(p.stem for p in requirements_dir.glob("*.md"))


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def MajorRequirementsLookup(major: str) -> str:
    """
    Look up the graduation requirements for a Duke Kunshan University major.

    Given a major (and optional track) name, returns the full list of
    required and elective courses from the UG Bulletin (2023-2024).

    Pass major="list" to get the names of all available majors/tracks.
    Pass major="requirements for all majors" to retrieve the university-wide
    core requirements that every student must complete regardless of major.

    Examples of valid major strings:
        "data science"
        "computation and design / computer science"
        "behavioral science psychology"
        "global health biology"
        "requirements for all majors"
        "list"

    Args:
        major (str): Major (and optionally track) name, e.g. "data science".
                     Pass "list" to enumerate available majors.

    Returns:
        Markdown text of the major's requirements, or an error message when
        no match is found.
    """
    req_dir = Path(config.major_req_dir)
    with span_ctx_start(
        "MajorRequirementsLookup", OpenInferenceSpanKindValues.TOOL
    ) as span:
        span.set_attributes(
            {
                SpanAttributes.INPUT_VALUE: safe_json_dumps(dict(major=major)),
                SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
            }
        )

        try:
            if not req_dir.is_dir():
                raise FileNotFoundError(f"Requirements directory not found: {req_dir}")

            stems = _list_stems(req_dir)
            if not stems:
                raise FileNotFoundError(f"No requirement files found in {req_dir}")

            # Special: list all available majors
            if major.strip().lower() == "list":
                result = "Available DKU majors/tracks:\n" + "\n".join(
                    f"  - {s}" for s in stems
                )
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: result,
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.TEXT.value,
                    }
                )
                span.set_status(Status(StatusCode.OK))
                return result

            matched = _best_match(major, stems)
            if matched is None:
                result = (
                    f"No matching major found for '{major}'. "
                    "Call with major='list' to see all available majors."
                )
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: result,
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.TEXT.value,
                    }
                )
                span.set_status(Status(StatusCode.OK))
                return result

            md_path = req_dir / f"{matched}.md"
            content = md_path.read_text(encoding="utf-8")
            result = f"# Requirements: {matched}\n\n{content}"

            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(matched_file=matched, char_count=len(result))
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
            return result

        except Exception as e:
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(error=str(e))),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.ERROR), str(e))
            raise e


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    from chatdku.setup import use_phoenix

    use_phoenix()

    parser = argparse.ArgumentParser(description="Test MajorRequirementsLookup")
    parser.add_argument("--major", required=True, help="Major name to look up")
    args = parser.parse_args()

    lookup = MajorRequirementsLookup(args.major)
    __import__("pprint").pprint(lookup)
