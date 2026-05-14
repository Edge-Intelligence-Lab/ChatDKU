from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class SourceRef:
    file_path: str
    file_name: str
    source_type: str
    source_url: str | None = None
    last_modified: str | None = None


@dataclass(slots=True)
class GroundedFact:
    label: str
    value: str
    evidence: str
    source_ref: str


@dataclass(slots=True)
class ContradictionNote:
    label: str
    status: str
    explanation: str
    conflicting_values: list[str] = field(default_factory=list)
    conflicting_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WikiPage:
    page_id: str
    title: str
    page_type: str
    domain: str
    tags: list[str]
    source_refs: list[SourceRef]
    ground_truth_refs: list[GroundedFact]
    cross_refs: list[str]
    output_path: str
    entity_names: list[str] = field(default_factory=list)
    node_count: int = 0
    status: str = "draft"
    contradiction_notes: list[ContradictionNote] = field(default_factory=list)
    summary: str = ""
    source_log: list[str] = field(default_factory=list)
    reference_context: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    last_updated: str = field(default_factory=utc_now_iso)
