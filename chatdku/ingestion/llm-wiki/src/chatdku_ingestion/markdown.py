from __future__ import annotations

from .models import WikiPage


def _render_domain_breakdown(pages: list[WikiPage]) -> str:
    by_domain: dict[str, list[WikiPage]] = {}
    for page in pages:
        by_domain.setdefault(page.domain, []).append(page)

    lines = []
    for domain in sorted(by_domain):
        pages_in_domain = by_domain[domain]
        lines.append(
            f"- `{domain}` | sources: {len(pages_in_domain)} | sample: "
            + ", ".join(f"`{page.page_id}`" for page in pages_in_domain[:5])
        )
    return "\n".join(lines) or "- No domain data."


def _render_source_refs(page: WikiPage) -> str:
    return "\n".join(
        [
            (
                f"- data_path: `{ref.file_path}` | file_name: `{ref.file_name}` | "
                f"source_type: `{ref.source_type}` | last_modified: `{ref.last_modified or ''}`"
            )
            for ref in page.source_refs
        ]
    ) or "- No source refs."


def _render_facts(page: WikiPage) -> str:
    return "\n".join(
        [
            (
                f"- [{fact.label}] {fact.value}\n"
                f"  - evidence: {fact.evidence}\n"
                f"  - source_ref: `{fact.source_ref}`"
            )
            for fact in page.ground_truth_refs
        ]
    ) or "- No grounded facts extracted."


def _render_contradictions(page: WikiPage) -> str:
    return "\n".join(
        [
            (
                f"- label: `{note.label}` | status: `{note.status}`\n"
                f"  - note: {note.explanation}\n"
                f"  - refs: {', '.join(f'`{ref}`' for ref in note.conflicting_refs)}"
            )
            for note in page.contradiction_notes
        ]
    ) or "- None detected."


def _render_source_log(page: WikiPage) -> str:
    return "\n".join([f"- {item}" for item in page.source_log]) or "- No source log."


def _render_context(page: WikiPage) -> str:
    return "\n".join([f"- {item}" for item in page.reference_context]) or "- Not available."


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
        "",
        f"- nodes_path: `{nodes_path}`",
        f"- output_dir: `{output_dir}`",
        f"- total_nodes: {total_nodes}",
        f"- total_sources: {len(pages)}",
        f"- validation_issues: {len(issues)}",
        "",
        "## Domain Breakdown",
        "",
        _render_domain_breakdown(pages),
        "",
        "## Source Inventory",
        "",
    ]

    for page in sorted(pages, key=lambda item: item.title.lower()):
        lines.extend(
            [
                f"### {page.title}",
                "",
                f"- page_id: `{page.page_id}`",
                f"- domain: `{page.domain}`",
                f"- status: `{page.status}`",
                f"- node_count: {page.node_count}",
                f"- last_updated: `{page.last_updated}`",
                "",
                "#### Source Refs",
                "",
                _render_source_refs(page),
                "",
                "#### Source Log",
                "",
                _render_source_log(page),
                "",
                "#### Digest",
                "",
                page.summary or "No digest generated.",
                "",
                "#### Verified Facts",
                "",
                _render_facts(page),
                "",
                "#### Contradictions",
                "",
                _render_contradictions(page),
                "",
                "#### Reference Context",
                "",
                _render_context(page),
                "",
            ]
        )

    lines.extend(
        [
            "## Validation",
            "",
            ("\n".join(f"- {issue}" for issue in issues) if issues else "- No issues detected."),
            "",
        ]
    )
    return "\n".join(lines)
