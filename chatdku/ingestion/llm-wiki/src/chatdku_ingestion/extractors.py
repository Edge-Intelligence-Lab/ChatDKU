from __future__ import annotations

import re
from collections import defaultdict

from .models import ContradictionNote, GroundedFact

FACT_PATTERN = re.compile(
    r"(?im)^\s*(deadline|requirement|contact|policy|scope)\s*[:\-]\s*(.+?)\s*$"
)


def extract_grounded_facts(
    text: str,
    source_ref: str,
    max_facts: int = 12,
) -> list[GroundedFact]:
    facts: list[GroundedFact] = []
    for match in FACT_PATTERN.finditer(text):
        label = match.group(1).strip().lower()
        value = match.group(2).strip()
        evidence = match.group(0).strip()
        if not value:
            continue
        facts.append(
            GroundedFact(
                label=label,
                value=value[:300],
                evidence=evidence[:400],
                source_ref=source_ref,
            )
        )
        if len(facts) >= max_facts:
            break
    return facts


def detect_contradictions(facts: list[GroundedFact]) -> list[ContradictionNote]:
    by_label: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for fact in facts:
        by_label[fact.label][fact.value.lower()].add(fact.source_ref)

    notes: list[ContradictionNote] = []
    for label, value_map in by_label.items():
        if len(value_map) <= 1:
            continue
        refs = sorted({ref for refs in value_map.values() for ref in refs})
        notes.append(
            ContradictionNote(
                label=label,
                status="unresolved",
                explanation=(
                    f"Found {len(value_map)} conflicting `{label}` values "
                    "across source-backed facts."
                ),
                conflicting_refs=refs,
            )
        )
    return notes
