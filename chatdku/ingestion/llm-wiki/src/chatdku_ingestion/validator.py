from __future__ import annotations

from collections import Counter, defaultdict

from .models import WikiPage


def validate_pages(pages: list[WikiPage]) -> list[str]:
    issues: list[str] = []
    seen_ids: set[str] = set()
    path_to_page_ids: dict[str, set[str]] = defaultdict(set)
    inbound_links: Counter[str] = Counter()
    known_ids = {page.page_id for page in pages}

    for page in pages:
        if page.page_id in seen_ids:
            issues.append(f"duplicate_page_id: {page.page_id}")
        seen_ids.add(page.page_id)

        if not page.output_path:
            issues.append(f"missing_output_path: {page.page_id}")

        if not page.source_refs:
            issues.append(f"missing_source_refs: {page.page_id}")

        if not page.summary.strip():
            issues.append(f"missing_summary: {page.page_id}")

        for source_ref in page.source_refs:
            if not source_ref.file_path:
                issues.append(f"missing_source_path: {page.page_id}")
                continue
            path_to_page_ids[source_ref.file_path].add(page.page_id)

        for fact in page.ground_truth_refs:
            if not fact.source_ref:
                issues.append(f"fact_without_source_ref: {page.page_id}")

        for ref in page.cross_refs:
            if ref not in known_ids:
                issues.append(f"broken_cross_ref: {page.page_id} -> {ref}")
            else:
                inbound_links[ref] += 1

    for file_path, page_ids in path_to_page_ids.items():
        source_pages = [page_id for page_id in page_ids if not page_id.startswith("entity-")]
        if len(source_pages) > 1:
            issues.append(
                "duplicate_source_path: "
                f"{file_path} -> {', '.join(sorted(source_pages))}"
            )

    for page in pages:
        if page.page_type == "entity" and inbound_links.get(page.page_id, 0) == 0:
            issues.append(f"orphan_entity_page: {page.page_id}")
        if any(note.status != "resolved" for note in page.contradiction_notes):
            issues.append(f"unresolved_contradiction: {page.page_id}")

    return issues
