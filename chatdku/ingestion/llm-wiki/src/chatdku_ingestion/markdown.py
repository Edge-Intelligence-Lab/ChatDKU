from __future__ import annotations

import os
from pathlib import Path

from .models import WikiPage


def _yaml_list(items: list[str], indent: int = 0) -> list[str]:
    prefix = " " * indent
    if not items:
        return [prefix + "[]"]
    return [f'{prefix}- "{item.replace(chr(34), chr(39))}"' for item in items]


def _frontmatter(page: WikiPage) -> str:
    lines = [
        "---",
        f'title: "{page.title.replace(chr(34), chr(39))}"',
        f'page_id: "{page.page_id}"',
        f'type: "{page.page_type}"',
        f'domain: "{page.domain}"',
        f'status: "{page.status}"',
        f'last_updated: "{page.last_updated}"',
        f"node_count: {page.node_count}",
        "tags:",
        *_yaml_list(page.tags, indent=2),
        "entities:",
        *_yaml_list(page.entity_names, indent=2),
        "source_paths:",
        *_yaml_list([ref.file_path for ref in page.source_refs], indent=2),
        "---",
    ]
    return "\n".join(lines)


def _relative_link(current: WikiPage, target: WikiPage) -> str:
    rel = os.path.relpath(target.output_path, start=str(Path(current.output_path).parent))
    return f"[{target.title}]({rel})"


def _render_links(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    links = [_relative_link(page, pages_by_id[ref]) for ref in page.cross_refs if ref in pages_by_id]
    return "\n".join(f"- {link}" for link in links) or "- None"


def _render_source_refs(page: WikiPage) -> str:
    lines = []
    for ref in page.source_refs:
        lines.append(
            f"- `{ref.file_path}` | file_name: `{ref.file_name}` | "
            f"source_type: `{ref.source_type}` | last_modified: `{ref.last_modified or ''}`"
        )
    return "\n".join(lines) or "- None"


def _render_facts(page: WikiPage) -> str:
    lines = []
    for fact in page.ground_truth_refs:
        lines.append(f"- **{fact.label}**: {fact.value}")
        lines.append(f"  - evidence: {fact.evidence}")
        lines.append(f"  - source_ref: `{fact.source_ref}`")
    return "\n".join(lines) or "- None"


def _render_contradictions(page: WikiPage) -> str:
    lines = []
    for note in page.contradiction_notes:
        lines.append(f"- **{note.label}** | status: `{note.status}`")
        lines.append(f"  - note: {note.explanation}")
        if note.conflicting_values:
            lines.append(
                "  - values: " + ", ".join(f"`{value}`" for value in note.conflicting_values)
            )
        if note.conflicting_refs:
            lines.append("  - refs: " + ", ".join(f"`{ref}`" for ref in note.conflicting_refs))
    return "\n".join(lines) or "- None"


def _render_source_log(page: WikiPage) -> str:
    return "\n".join(f"- {item}" for item in page.source_log) or "- None"


def _render_context(page: WikiPage) -> str:
    return "\n".join(f"- {item}" for item in page.reference_context) or "- None"


def render_source_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## Summary",
        page.summary or "No summary generated.",
        "",
        "## Grounded Facts",
        _render_facts(page),
        "",
        "## Source Refs",
        _render_source_refs(page),
        "",
        "## Connections",
        _render_links(page, pages_by_id),
        "",
        "## Contradictions",
        _render_contradictions(page),
        "",
        "## Source Log",
        _render_source_log(page),
        "",
        "## Reference Context",
        _render_context(page),
    ]
    return "\n".join(lines).strip() + "\n"


def render_entity_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## Summary",
        page.summary or "No summary generated.",
        "",
        "## Supporting Sources",
        _render_source_refs(page),
        "",
        "## Grounded Facts",
        _render_facts(page),
        "",
        "## Connections",
        _render_links(page, pages_by_id),
        "",
        "## Contradictions",
        _render_contradictions(page),
    ]
    return "\n".join(lines).strip() + "\n"


def render_index(pages: list[WikiPage]) -> str:
    sources = [page for page in pages if page.page_type == "source"]
    entities = [page for page in pages if page.page_type == "entity"]
    lines = [
        "# ChatDKU Wiki Index",
        "",
        "## Overview",
        "- [Overview](overview.md)",
        "- [Main Build Report](main.md)",
        "- [Validation Report](validation_report.md)",
        "",
        "## Sources",
    ]
    for page in sorted(sources, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    lines.extend(["", "## Entities"])
    for page in sorted(entities, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    return "\n".join(lines).strip() + "\n"


def render_overview(pages: list[WikiPage], issues: list[str]) -> str:
    sources = [page for page in pages if page.page_type == "source"]
    entities = [page for page in pages if page.page_type == "entity"]
    by_domain: dict[str, int] = {}
    for page in sources:
        by_domain[page.domain] = by_domain.get(page.domain, 0) + 1

    lines = [
        "# ChatDKU Wiki Overview",
        "",
        "## Snapshot",
        f"- source_pages: {len(sources)}",
        f"- entity_pages: {len(entities)}",
        f"- validation_issues: {len(issues)}",
        "",
        "## Domain Coverage",
    ]
    for domain, count in sorted(by_domain.items()):
        lines.append(f"- `{domain}`: {count} sources")

    lines.extend(["", "## Notable Entities"])
    for page in sorted(entities, key=lambda item: (-len(item.source_refs), item.title.lower()))[:15]:
        lines.append(f"- [{page.title}]({page.output_path}) - supported by {len(page.source_refs)} source(s)")
    return "\n".join(lines).strip() + "\n"


def render_main_document(
    pages: list[WikiPage],
    *,
    nodes_path: str,
    total_nodes: int,
    output_dir: str,
    issues: list[str],
) -> str:
    sources = [page for page in pages if page.page_type == "source"]
    entities = [page for page in pages if page.page_type == "entity"]
    lines = [
        "# ChatDKU Wiki Main",
        "",
        "## Build Log",
        f"- nodes_path: `{nodes_path}`",
        f"- output_dir: `{output_dir}`",
        f"- total_nodes: {total_nodes}",
        f"- source_pages: {len(sources)}",
        f"- entity_pages: {len(entities)}",
        f"- validation_issues: {len(issues)}",
        "",
        "## Key Outputs",
        "- [Index](index.md)",
        "- [Overview](overview.md)",
        "- [Validation Report](validation_report.md)",
        "",
        "## Source Inventory",
    ]
    for page in sorted(sources, key=lambda item: item.title.lower()):
        lines.append(
            f"- [{page.title}]({page.output_path}) | domain: `{page.domain}` | "
            f"facts: {len(page.ground_truth_refs)} | links: {len(page.cross_refs)}"
        )

    lines.extend(["", "## Entity Inventory"])
    for page in sorted(entities, key=lambda item: item.title.lower()):
        lines.append(
            f"- [{page.title}]({page.output_path}) | sources: {len(page.source_refs)} | "
            f"links: {len(page.cross_refs)}"
        )

    lines.extend(["", "## Validation"])
    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- No issues detected.")
    return "\n".join(lines).strip() + "\n"


def render_validation_report(issues: list[str]) -> str:
    lines = ["# Validation Report", ""]
    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- No issues detected.")
    return "\n".join(lines).strip() + "\n"
