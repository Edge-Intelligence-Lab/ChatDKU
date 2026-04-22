from __future__ import annotations

import hashlib
import re
from pathlib import Path


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return value or "untitled"


def infer_domain(file_path: str) -> str:
    lower = file_path.lower()
    if "admission" in lower:
        return "admissions"
    if "academic" in lower or "curriculum" in lower:
        return "academics"
    if "event" in lower:
        return "events"
    if "service" in lower:
        return "services"
    if "office" in lower or "admin" in lower:
        return "administration"
    if "student" in lower or "campus" in lower:
        return "student-life"
    return "general"


def first_sentences(text: str, max_sentences: int = 4) -> str:
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
