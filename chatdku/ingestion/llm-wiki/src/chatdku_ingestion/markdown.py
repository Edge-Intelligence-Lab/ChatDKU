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
        "topic_family:",
        *_yaml_list(page.topic_families, indent=2),
        "audience:",
        *_yaml_list(page.audience, indent=2),
        "source_surfaces:",
        *_yaml_list(page.source_surfaces, indent=2),
    ]
    if page.canonical_source_cluster:
        lines.append(f'canonical_source_cluster: "{page.canonical_source_cluster}"')
    if page.cluster_status:
        lines.append(f'cluster_status: "{page.cluster_status}"')
    lines.extend(
        [
            "source_paths:",
            *_yaml_list([ref.file_path for ref in page.source_refs], indent=2),
            "authority_sources:",
            *_yaml_list(page.authority_sources, indent=2),
            "---",
        ]
    )
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


def render_topic_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## One-Line Summary",
        page.summary or "No summary generated.",
        "",
        "## Why This Page Exists",
        (
            "This is a compact DKU topic index page. Read this first to orient to the topic, "
            "then open the best detailed source when needed."
        ),
        "",
        "## Quick Orientation",
        *([f"- {item}" for item in page.reference_context] or ["- Not available."]),
        "",
        "## Best Sources To Open Next",
        *([f"- `{item}`" for item in page.preferred_detail_sources] or ["- Not available."]),
        "",
        "## Related Authority Sources",
        *([f"- `{item}`" for item in page.authority_sources] or ["- None."]),
        "",
        "## Related Topics",
        _render_links(page, pages_by_id),
        "",
        "## Source Cluster Status",
        f"- `{page.cluster_status or 'stable'}`",
    ]
    return "\n".join(lines).strip() + "\n"


def render_cluster_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## Cluster Summary",
        page.summary or "No summary generated.",
        "",
        "## Authority Order",
        *([f"- `{item}`" for item in page.source_log] or ["- Not available."]),
        "",
        "## Included Sources",
        _render_source_refs(page),
        "",
        "## Best Entry Sources",
        *([f"- `{item}`" for item in page.preferred_detail_sources] or ["- Not available."]),
        "",
        "## Related Pages",
        _render_links(page, pages_by_id),
        "",
        "## Notes On Overlap",
        f"- cluster_status: `{page.cluster_status or 'stable'}`",
    ]
    return "\n".join(lines).strip() + "\n"


def render_authority_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## One-Line Summary",
        page.summary or "No summary generated.",
        "",
        "## Why This Authority Matters",
        (
            "This page represents a cross-topic authority source. "
            "Use it when a topic page needs the most comprehensive official reference, "
            "but prefer narrower topic sources first when they exist."
        ),
        "",
        "## Best Topics To Reach From Here",
        _render_links(page, pages_by_id),
        "",
        "## Source Refs",
        _render_source_refs(page),
    ]
    return "\n".join(lines).strip() + "\n"


def render_service_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## One-Line Summary",
        page.summary or "No summary generated.",
        "",
        "## What This Service Helps With",
        *([f"- {item}" for item in page.reference_context] or ["- Not available."]),
        "",
        "## Best Sources To Open",
        *([f"- `{item}`" for item in page.preferred_detail_sources] or ["- Not available."]),
        "",
        "## Related Topic Indexes",
        _render_links(page, pages_by_id),
    ]
    return "\n".join(lines).strip() + "\n"


def render_timeline_page(page: WikiPage, pages_by_id: dict[str, WikiPage]) -> str:
    lines = [
        _frontmatter(page),
        "",
        f"# {page.title}",
        "",
        "## Cycle Summary",
        page.summary or "No summary generated.",
        "",
        "## Best Calendar / Handbook Sources",
        *([f"- `{item}`" for item in page.preferred_detail_sources] or ["- Not available."]),
        "",
        "## Related Topic Indexes",
        _render_links(page, pages_by_id),
    ]
    return "\n".join(lines).strip() + "\n"


def render_index(pages: list[WikiPage]) -> str:
    topics = [page for page in pages if page.page_type == "topic_index"]
    authorities = [page for page in pages if page.page_type == "authority_index"]
    services = [page for page in pages if page.page_type == "service_index"]
    timelines = [page for page in pages if page.page_type == "timeline_index"]
    clusters = [page for page in pages if page.page_type == "source_cluster"]

    lines = [
        "# ChatDKU Wiki Index",
        "",
        "## Overview",
        "- [Overview](overview.md)",
        "- [Main Build Report](main.md)",
        "- [Validation Report](validation_report.md)",
        "",
        "## Topic Indexes",
    ]
    for page in sorted(topics, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    lines.extend(["", "## Authority Sources"])
    for page in sorted(authorities, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    lines.extend(["", "## Service Indexes"])
    for page in sorted(services, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    lines.extend(["", "## Timeline Indexes"])
    for page in sorted(timelines, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    lines.extend(["", "## Source Clusters"])
    for page in sorted(clusters, key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) - {page.summary[:140]}")
    return "\n".join(lines).strip() + "\n"


def render_overview(pages: list[WikiPage], issues: list[str]) -> str:
    topics = [page for page in pages if page.page_type == "topic_index"]
    authorities = [page for page in pages if page.page_type == "authority_index"]
    services = [page for page in pages if page.page_type == "service_index"]
    timelines = [page for page in pages if page.page_type == "timeline_index"]
    clusters = [page for page in pages if page.page_type == "source_cluster"]
    by_family: dict[str, int] = {}
    for page in topics:
        for family in page.topic_families:
            by_family[family] = by_family.get(family, 0) + 1

    lines = [
        "# ChatDKU Wiki Overview",
        "",
        "## Snapshot",
        f"- topic_pages: {len(topics)}",
        f"- authority_pages: {len(authorities)}",
        f"- cluster_pages: {len(clusters)}",
        f"- service_pages: {len(services)}",
        f"- timeline_pages: {len(timelines)}",
        f"- validation_issues: {len(issues)}",
        "",
        "## Topic Family Coverage",
    ]
    for family, count in sorted(by_family.items()):
        lines.append(f"- `{family}`: {count} topic page(s)")
    return "\n".join(lines).strip() + "\n"


def render_main_document(
    pages: list[WikiPage],
    *,
    nodes_path: str,
    total_nodes: int,
    output_dir: str,
    issues: list[str],
) -> str:
    lines = [
        "# ChatDKU Wiki Main",
        "",
        "## Build Log",
        f"- nodes_path: `{nodes_path}`",
        f"- output_dir: `{output_dir}`",
        f"- total_nodes: {total_nodes}",
        f"- total_pages: {len(pages)}",
        f"- validation_issues: {len(issues)}",
        "",
        "## Key Outputs",
        "- [Index](index.md)",
        "- [Overview](overview.md)",
        "- [Validation Report](validation_report.md)",
        "",
        "## Topic Inventory",
    ]
    for page in sorted((p for p in pages if p.page_type == "topic_index"), key=lambda item: item.title.lower()):
        lines.append(
            f"- [{page.title}]({page.output_path}) | family: `{', '.join(page.topic_families)}` | "
            f"cluster: `{page.canonical_source_cluster or ''}`"
        )
    lines.extend(["", "## Authority Inventory"])
    for page in sorted((p for p in pages if p.page_type == "authority_index"), key=lambda item: item.title.lower()):
        lines.append(f"- [{page.title}]({page.output_path}) | surfaces: `{', '.join(page.source_surfaces)}`")
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
