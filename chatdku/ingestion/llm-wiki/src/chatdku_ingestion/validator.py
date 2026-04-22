from __future__ import annotations

from collections import defaultdict

from .models import WikiPage


def validate_pages(pages: list[WikiPage]) -> list[str]:
    issues: list[str] = []
    seen_ids: set[str] = set()
    path_to_page_ids: dict[str, set[str]] = defaultdict(set)

    for page in pages:
        if page.page_id in seen_ids:
            issues.append(f"duplicate_page_id: {page.page_id}")
        seen_ids.add(page.page_id)

        if not page.source_refs:
            issues.append(f"missing_source_refs: {page.page_id}")

        if not page.summary.strip():
            issues.append(f"missing_summary: {page.page_id}")

        if len(page.source_refs) != 1:
            issues.append(f"unexpected_source_ref_count: {page.page_id}:{len(page.source_refs)}")

        for source_ref in page.source_refs:
            if not source_ref.file_path:
                issues.append(f"missing_source_path: {page.page_id}")
                continue
            path_to_page_ids[source_ref.file_path].add(page.page_id)

        for fact in page.ground_truth_refs:
            if not fact.source_ref:
                issues.append(f"fact_without_source_ref: {page.page_id}")

    for file_path, page_ids in path_to_page_ids.items():
        if len(page_ids) > 1:
            issues.append(
                "duplicate_source_path: "
                f"{file_path} -> {', '.join(sorted(page_ids))}"
            )

    return issues
