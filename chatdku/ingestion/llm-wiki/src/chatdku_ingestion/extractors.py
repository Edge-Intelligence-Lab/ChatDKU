from __future__ import annotations

import re

from .models import GroundedFact
from .utils import looks_garbled_text, unique_preserve_order

FACT_PATTERN = re.compile(
    r"(?im)^\s*(deadline|requirement|contact|policy|scope|office|email|phone)\s*[:\-]\s*(.+?)\s*$"
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\-\s]{6,}\d)")


def extract_grounded_facts(
    text: str,
    source_ref: str,
    max_facts: int = 16,
) -> list[GroundedFact]:
    if looks_garbled_text(text):
        return []
    facts: list[GroundedFact] = []
    seen_pairs: set[tuple[str, str]] = set()

    def add_fact(label: str, value: str, evidence: str) -> None:
        normalized_label = label.strip().lower()
        normalized_value = value.strip()
        key = (normalized_label, normalized_value.lower())
        if not normalized_value or key in seen_pairs:
            return
        seen_pairs.add(key)
        facts.append(
            GroundedFact(
                label=normalized_label,
                value=normalized_value[:300],
                evidence=evidence.strip()[:400],
                source_ref=source_ref,
            )
        )

    for match in FACT_PATTERN.finditer(text):
        add_fact(match.group(1), match.group(2), match.group(0))
        if len(facts) >= max_facts:
            return facts

    for email in unique_preserve_order(EMAIL_PATTERN.findall(text)):
        add_fact("email", email, email)
        if len(facts) >= max_facts:
            return facts

    for phone in unique_preserve_order([item.strip() for item in PHONE_PATTERN.findall(text)]):
        digits_only = "".join(ch for ch in phone if ch.isdigit())
        if len(digits_only) < 7:
            continue
        if re.fullmatch(r"\d{4}-\d{4}", phone):
            continue
        add_fact("phone", phone, phone)
        if len(facts) >= max_facts:
            return facts

    return facts


def extract_candidate_entities(text: str, metadata: dict) -> list[str]:
    candidates: list[str] = []
    file_path = str(metadata.get("file_path") or "")
    organization = metadata.get("organization")
    if organization:
        candidates.append(str(organization).strip())

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    for suffix in [" | DKU Faculty", "| DKU Faculty", " | Duke Kunshan University"]:
        if first_line.endswith(suffix):
            first_line = first_line[: -len(suffix)].strip()
    if (
        first_line
        and len(first_line) <= 100
        and 1 < len(first_line.split()) <= 8
        and any(token in file_path.lower() for token in ["faculty", "staff", "profile"])
    ):
        candidates.append(first_line)

    return unique_preserve_order(candidates)
