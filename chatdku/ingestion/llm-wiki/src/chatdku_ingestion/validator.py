from __future__ import annotations

from collections import Counter

from .models import WikiPage

AUTHORITY_REQUIRED_FAMILIES = {
    "major_track_program",
    "academic_policy",
    "registration_planning",
    "reference_catalog",
}


def validate_pages(pages: list[WikiPage]) -> list[str]:
    issues: list[str] = []
    seen_ids: set[str] = set()
    inbound_links: Counter[str] = Counter()
    known_ids = {page.page_id for page in pages}

    for page in pages:
        if page.page_id in seen_ids:
            issues.append(f"duplicate_page_id: {page.page_id}")
        seen_ids.add(page.page_id)

        if not page.output_path:
            issues.append(f"missing_output_path: {page.page_id}")

        if not page.summary.strip():
            issues.append(f"missing_summary: {page.page_id}")

        if page.page_type == "topic_index" and not page.canonical_source_cluster:
            issues.append(f"missing_canonical_source_cluster: {page.page_id}")

        if page.page_type == "source_cluster" and not page.source_refs:
            issues.append(f"empty_source_cluster: {page.page_id}")

        if page.page_type == "topic_index" and len(page.cross_refs) < 2:
            issues.append(f"weak_topic_interconnection: {page.page_id}")

        if (
            page.page_type == "topic_index"
            and set(page.topic_families) & AUTHORITY_REQUIRED_FAMILIES
            and not page.authority_sources
        ):
            issues.append(f"missing_authority_reference: {page.page_id}")

        for ref in page.cross_refs:
            if ref not in known_ids:
                issues.append(f"broken_cross_ref: {page.page_id} -> {ref}")
            else:
                inbound_links[ref] += 1

    for page in pages:
        if page.page_type == "source_cluster" and inbound_links.get(page.page_id, 0) == 0:
            issues.append(f"orphan_cluster_page: {page.page_id}")

    return issues
