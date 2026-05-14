from __future__ import annotations

import hashlib
import re
from pathlib import Path


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return value or "untitled"


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def looks_garbled_text(text: str) -> bool:
    if not text:
        return False
    sample = text[:1200]
    printable = sum(1 for ch in sample if ch.isprintable() or ch.isspace())
    ratio = printable / max(len(sample), 1)
    control_chars = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
    return ratio < 0.85 or control_chars > 8


def infer_domain(file_path: str) -> str:
    lower = file_path.lower()
    if "admission" in lower:
        return "admissions"
    if any(token in lower for token in ["academic", "curriculum", "faculty", "course"]):
        return "academics"
    if "event" in lower:
        return "events"
    if any(token in lower for token in ["service", "support"]):
        return "services"
    if any(token in lower for token in ["office", "admin", "policy"]):
        return "administration"
    if any(token in lower for token in ["student", "campus", "housing"]):
        return "student-life"
    return "general"


def first_sentences(text: str, max_sentences: int = 4) -> str:
    if looks_garbled_text(text):
        return "Low-quality extracted text detected. Source likely needs parser cleanup before wiki synthesis."
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return "No summary content extracted."
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return " ".join(parts[:max_sentences])[:1200]


def doc_key_from_node(node: dict) -> str:
    metadata = node.get("metadata", {}) or {}
    return (
        metadata.get("file_path")
        or node.get("ref_doc_id")
        or metadata.get("file_name")
        or node.get("id_")
        or node.get("node_id")
        or "unknown"
    )


def file_name_from_doc_key(doc_key: str) -> str:
    return Path(doc_key).name or "unknown-source"


def page_id_from_doc_key(doc_key: str) -> str:
    normalized = str(Path(doc_key))
    stem = Path(normalized).stem or "source"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    return f"{slugify(stem)}-{digest}"


def entity_page_id(name: str) -> str:
    return f"entity-{slugify(name)}"


def title_from_source(file_name: str, text: str, file_path: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    for suffix in [" | DKU Faculty", "| DKU Faculty", " | Duke Kunshan University"]:
        if first_line.endswith(suffix):
            first_line = first_line[: -len(suffix)].strip()
    if (
        first_line
        and len(first_line) <= 100
        and 1 < len(first_line.split()) <= 12
        and file_name.lower() == "index.html"
    ):
        return first_line
    if file_name.lower() == "index.html":
        parts = [part for part in Path(file_path).parts if part not in {"", "/"}]
        if len(parts) >= 2:
            return parts[-2].replace("-", " ").replace("_", " ").title()
    return file_name
