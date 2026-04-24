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

from chatdku.config import config
from chatdku.core.utils import span_ctx_start

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


def MajorRequirementsLookupOuter() -> callable:
    """Factory: reads the requirements directory once and bakes the stem list into
    the returned tool's docstring so the LM always sees the exact valid names."""
    req_dir = Path(config.major_req_dir)
    stems: list[str] = _list_stems(req_dir) if req_dir.is_dir() else []
    stems_list_str = "\n".join(f"  - {s}" for s in stems)

    def _not_found_msg(major: str) -> str:
        return (
            f"ERROR: '{major}' is not a recognised major name.\n"
            f"You must use one of the exact names listed below:\n{stems_list_str}"
        )

    def MajorRequirementsLookup(major: str) -> str:
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
                if not stems:
                    raise FileNotFoundError(
                        f"No requirement files found in {req_dir}"
                    )

                matched = _best_match(major, stems)
                if matched is None:
                    result = _not_found_msg(major)
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
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                            dict(error=str(e))
                        ),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
                span.set_status(Status(StatusCode.ERROR), str(e))
                raise e

    MajorRequirementsLookup.__doc__ = f"""
    Look up graduation requirements for a Duke Kunshan University major/track.

    You MUST pass one of the exact kebab-case major names listed below.
    Do NOT paraphrase or translate the name — copy it exactly as shown.

    Valid major names:
{stems_list_str}

    Also accepts "requirements-for-all-majors" for university-wide core requirements.

    If the name you pass does not match any entry in the list above, an error is
    returned with the full list of valid names so you can correct the call.

    Args:
        major (str): Exact kebab-case major name from the list above,
                     e.g. "computation-and-design-computer-science".

    Returns:
        Markdown text of the major requirements, or an error message with the
        list of valid names when the supplied name is not recognised.
    """

    return MajorRequirementsLookup


def MajorRequirementsLookup(major: str) -> str:
    """CLI helper — delegates to MajorRequirementsLookupOuter()."""
    return MajorRequirementsLookupOuter()(major)


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
