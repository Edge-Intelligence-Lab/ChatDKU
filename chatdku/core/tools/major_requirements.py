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

from chatdku.core.utils import span_ctx_start

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(s: str) -> set[str]:
    """Lowercase, drop punctuation/separators, return word-token set."""
    s = s.lower()
    s = re.sub(r"[/\\&,\-]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return set(s.split())


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _best_match(query: str, stems: list[str]) -> str | None:
    """
    Return the filename stem that best matches *query* by Jaccard similarity
    on word tokens.  Returns None when no candidate shares any token with
    the query.
    """
    q_tokens = _tokenize(query)
    if not q_tokens:
        return None

    best_stem: str | None = None
    best_score = 0.0

    for stem in stems:
        c_tokens = _tokenize(stem)
        score = _jaccard(q_tokens, c_tokens)
        if score > best_score:
            best_score = score
            best_stem = stem

    return best_stem if best_score > 0.0 else None


def _list_stems(requirements_dir: Path) -> list[str]:
    return sorted(p.stem for p in requirements_dir.glob("*.md"))


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def MajorRequirementsLookupOuter(requirements_dir: str):
    """
    DSPy tool factory for looking up DKU major/track degree requirements.

    Args:
        requirements_dir: Path to the directory containing per-major
            Markdown files from the UG Bulletin.
    """
    req_dir = Path(requirements_dir)

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
                    raise FileNotFoundError(
                        f"Requirements directory not found: {req_dir}"
                    )

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
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                            dict(error=str(e))
                        ),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
                span.set_status(Status(StatusCode.ERROR), str(e))
                raise

    return MajorRequirementsLookup


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test MajorRequirementsLookup")
    parser.add_argument(
        "--dir",
        default="/datapool/chatdku_external_data/doc_testing/output/ug_bulletin_2023-2024",
        help="Path to the requirements markdown directory",
    )
    parser.add_argument("--major", required=True, help="Major name to look up")
    args = parser.parse_args()

    lookup = MajorRequirementsLookupOuter(args.dir)
    print(lookup(args.major))
