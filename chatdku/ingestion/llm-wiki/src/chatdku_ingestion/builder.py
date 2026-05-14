from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .extractors import extract_candidate_entities, extract_grounded_facts
from .io import clear_markdown_dir, ensure_layout, load_nodes, write_json, write_text
from .markdown import (
    render_entity_page,
    render_index,
    render_main_document,
    render_overview,
    render_source_page,
    render_validation_report,
)
from .models import ContradictionNote, SourceRef, WikiPage
from .utils import (
    doc_key_from_node,
    entity_page_id,
    file_name_from_doc_key,
    first_sentences,
    infer_domain,
    page_id_from_doc_key,
    slugify,
    title_from_source,
    unique_preserve_order,
)
from .validator import validate_pages

CONTRADICTION_LABELS = {"deadline", "requirement", "policy", "scope", "office"}


def _group_nodes_by_source(nodes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        grouped[doc_key_from_node(node)].append(node)
    return grouped


def _guess_source_type(metadata: dict) -> str:
    if metadata.get("is_event") is True or metadata.get("event_url"):
        return "event"
    file_type = str(metadata.get("file_type") or "").lower()
    if file_type:
        return file_type
    return "doc"


def _build_source_page(doc_key: str, doc_nodes: list[dict]) -> WikiPage:
    first_meta = (doc_nodes[0].get("metadata", {}) or {}) if doc_nodes else {}
    texts = [str(node.get("text", "")).strip() for node in doc_nodes if node.get("text")]
    merged_text = "\n".join(texts)
    file_name = first_meta.get("file_name") or file_name_from_doc_key(doc_key)
    file_path = str(first_meta.get("file_path") or doc_key)
    title = title_from_source(file_name, merged_text, file_path)
    source_type = _guess_source_type(first_meta)
    domain = infer_domain(file_path)
    page_id = page_id_from_doc_key(file_path)

    source_ref = SourceRef(
        file_path=file_path,
        file_name=file_name,
        source_type=source_type,
        source_url=first_meta.get("source_url") or first_meta.get("event_url"),
        last_modified=first_meta.get("last_modified_date"),
    )

    facts = extract_grounded_facts(merged_text, source_ref=source_ref.file_path)
    entities = extract_candidate_entities(merged_text, first_meta)
    tags = unique_preserve_order(
        [
            domain,
            source_type,
            str(first_meta.get("access_type") or ""),
            str(first_meta.get("role") or ""),
        ]
    )
    source_log = [
        f"doc_key: `{doc_key}`",
        f"file_type: `{first_meta.get('file_type', '')}`",
        f"page_number: `{first_meta.get('page_number', '')}`",
        f"access_type: `{first_meta.get('access_type', '')}`",
        f"role: `{first_meta.get('role', '')}`",
        f"organization: `{first_meta.get('organization', '')}`",
        f"user_id: `{first_meta.get('user_id', '')}`",
        f"chunk_count: `{len(doc_nodes)}`",
    ]

    return WikiPage(
        page_id=page_id,
        title=title,
        page_type="source",
        domain=domain,
        tags=tags,
        source_refs=[source_ref],
        ground_truth_refs=facts,
        cross_refs=[],
        output_path=f"sources/{page_id}.md",
        entity_names=entities,
        node_count=len(doc_nodes),
        status="verified" if facts else "draft",
        summary=first_sentences(merged_text),
        source_log=source_log,
        reference_context=[text[:240] for text in texts[:5]],
        open_questions=[] if facts else ["No deterministic grounded facts detected yet."],
    )


def _build_entity_pages(source_pages: list[WikiPage]) -> list[WikiPage]:
    entity_to_sources: dict[str, list[WikiPage]] = defaultdict(list)
    for page in source_pages:
        for entity_name in page.entity_names:
            entity_to_sources[entity_name].append(page)

    entity_pages: list[WikiPage] = []
    for entity_name, pages in sorted(entity_to_sources.items(), key=lambda item: item[0].lower()):
        source_refs = unique_preserve_order([ref.file_path for page in pages for ref in page.source_refs])
        rendered_refs = [
            SourceRef(file_path=ref_path, file_name=Path(ref_path).name or ref_path, source_type="source")
            for ref_path in source_refs
        ]
        merged_facts = []
        for page in pages:
            merged_facts.extend(page.ground_truth_refs[:4])
        summary = (
            f"{entity_name} appears in {len(pages)} source page(s) across "
            f"{len({page.domain for page in pages})} domain(s)."
        )
        entity_pages.append(
            WikiPage(
                page_id=entity_page_id(entity_name),
                title=entity_name,
                page_type="entity",
                domain=pages[0].domain,
                tags=unique_preserve_order([page.domain for page in pages] + ["entity"]),
                source_refs=rendered_refs,
                ground_truth_refs=merged_facts[:10],
                cross_refs=[],
                output_path=f"entities/{slugify(entity_name)}.md",
                entity_names=[entity_name],
                node_count=sum(page.node_count for page in pages),
                status="verified" if merged_facts else "draft",
                summary=summary,
                source_log=[f"source_pages: {', '.join(page.page_id for page in pages[:8])}"],
                reference_context=[page.summary for page in pages[:5]],
            )
        )
    return entity_pages


def _attach_cross_refs(source_pages: list[WikiPage], entity_pages: list[WikiPage]) -> None:
    entity_lookup = {page.title: page.page_id for page in entity_pages}
    source_by_id = {page.page_id: page for page in source_pages}
    source_ids_by_entity: dict[str, list[str]] = defaultdict(list)

    for page in source_pages:
        for entity_name in page.entity_names:
            source_ids_by_entity[entity_name].append(page.page_id)

    for page in source_pages:
        related_sources: list[str] = []
        for entity_name in page.entity_names:
            related_sources.extend(source_ids_by_entity[entity_name])
        related_sources.extend(
            other.page_id for other in source_pages if other.domain == page.domain and other.page_id != page.page_id
        )
        entity_refs = [entity_lookup[name] for name in page.entity_names if name in entity_lookup]
        page.cross_refs = unique_preserve_order(entity_refs + related_sources)
        page.cross_refs = [ref for ref in page.cross_refs if ref != page.page_id][:10]

    entity_names_by_source: dict[str, list[str]] = {page.page_id: page.entity_names for page in source_pages}
    for entity_page in entity_pages:
        related_entity_names: list[str] = []
        source_refs: list[str] = []
        for source_page in source_pages:
            if entity_page.title not in source_page.entity_names:
                continue
            source_refs.append(source_page.page_id)
            related_entity_names.extend(
                name for name in entity_names_by_source[source_page.page_id] if name != entity_page.title
            )
        entity_links = [entity_lookup[name] for name in unique_preserve_order(related_entity_names) if name in entity_lookup]
        entity_page.cross_refs = unique_preserve_order(source_refs + entity_links)[:12]


def _attach_cluster_contradictions(source_pages: list[WikiPage], entity_pages: list[WikiPage]) -> None:
    source_by_id = {page.page_id: page for page in source_pages}
    page_notes: dict[str, list[ContradictionNote]] = defaultdict(list)

    clusters: dict[str, list[str]] = defaultdict(list)
    for entity_page in entity_pages:
        source_ids = [ref for ref in entity_page.cross_refs if ref in source_by_id]
        if len(source_ids) > 1:
            clusters[f"entity:{entity_page.title}"] = source_ids

    for page in source_pages:
        clusters[f"title:{slugify(page.title)}"].append(page.page_id)

    for cluster_name, page_ids in clusters.items():
        unique_page_ids = unique_preserve_order(page_ids)
        if len(unique_page_ids) <= 1:
            continue

        fact_index: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        value_index: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

        for page_id in unique_page_ids:
            for fact in source_by_id[page_id].ground_truth_refs:
                if fact.label not in CONTRADICTION_LABELS:
                    continue
                normalized_value = fact.value.lower()
                fact_index[fact.label][normalized_value].add(page_id)
                value_index[fact.label][normalized_value].append(fact.value)

        for label, values in fact_index.items():
            if len(values) <= 1:
                continue
            conflicting_page_ids = sorted({pid for pid_set in values.values() for pid in pid_set})
            display_values = [variants[0] for variants in value_index[label].values()]
            note = ContradictionNote(
                label=label,
                status="needs_review",
                explanation=(
                    f"Found {len(values)} distinct `{label}` values inside cluster `{cluster_name}` "
                    f"across {len(conflicting_page_ids)} source pages."
                ),
                conflicting_values=sorted(display_values)[:6],
                conflicting_refs=conflicting_page_ids,
            )
            for page_id in conflicting_page_ids:
                page_notes[page_id].append(note)

    for page in source_pages:
        page.contradiction_notes.extend(page_notes.get(page.page_id, []))

    for entity_page in entity_pages:
        related_source_ids = [ref for ref in entity_page.cross_refs if ref in source_by_id]
        notes: list[ContradictionNote] = []
        for source_id in related_source_ids:
            notes.extend(page_notes.get(source_id, []))
        entity_page.contradiction_notes = notes[:6]


def build_wiki(nodes_path: str | Path, output_dir: str | Path = ".") -> dict:
    nodes = load_nodes(nodes_path)
    paths = ensure_layout(output_dir)
    clear_markdown_dir(paths["sources"])
    clear_markdown_dir(paths["entities"])

    grouped = _group_nodes_by_source(nodes)
    source_pages = [_build_source_page(doc_key, doc_nodes) for doc_key, doc_nodes in grouped.items()]
    entity_pages = _build_entity_pages(source_pages)
    _attach_cross_refs(source_pages, entity_pages)
    _attach_cluster_contradictions(source_pages, entity_pages)

    all_pages = source_pages + entity_pages
    pages_by_id = {page.page_id: page for page in all_pages}

    for page in source_pages:
        write_text(paths["wiki"] / page.output_path, render_source_page(page, pages_by_id))
    for page in entity_pages:
        write_text(paths["wiki"] / page.output_path, render_entity_page(page, pages_by_id))

    issues = validate_pages(all_pages)

    write_text(paths["wiki"] / "index.md", render_index(all_pages))
    write_text(paths["wiki"] / "overview.md", render_overview(all_pages, issues))
    write_text(
        paths["wiki"] / "main.md",
        render_main_document(
            all_pages,
            nodes_path=str(Path(nodes_path)),
            total_nodes=len(nodes),
            output_dir=str(Path(output_dir)),
            issues=issues,
        ),
    )
    write_text(paths["wiki"] / "validation_report.md", render_validation_report(issues))

    page_catalog = [
        {
            "page_id": page.page_id,
            "title": page.title,
            "page_type": page.page_type,
            "domain": page.domain,
            "output_path": page.output_path,
            "source_count": len(page.source_refs),
            "fact_count": len(page.ground_truth_refs),
            "cross_ref_count": len(page.cross_refs),
            "entities": page.entity_names,
        }
        for page in all_pages
    ]
    graph_payload = {
        "nodes": [
            {
                "id": page.page_id,
                "title": page.title,
                "type": page.page_type,
                "domain": page.domain,
                "path": page.output_path,
            }
            for page in all_pages
        ],
        "edges": [
            {"source": page.page_id, "target": target, "relation": "related"}
            for page in all_pages
            for target in page.cross_refs
        ],
    }
    write_json(paths["graph"] / "pages.json", page_catalog)
    write_json(paths["graph"] / "graph.json", graph_payload)
    write_text(
        paths["graph"] / "graph.html",
        "<html><body><h1>Graph Placeholder</h1><p>Use graph.json or pages.json for downstream visualization.</p></body></html>\n",
    )

    return {
        "total_nodes": len(nodes),
        "total_source_pages": len(source_pages),
        "total_entity_pages": len(entity_pages),
        "issues": issues,
        "index_document": str(paths["wiki"] / "index.md"),
        "main_document": str(paths["wiki"] / "main.md"),
        "wiki_dir": str(paths["wiki"]),
    }
