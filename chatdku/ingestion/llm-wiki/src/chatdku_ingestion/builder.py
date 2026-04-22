from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .extractors import detect_contradictions, extract_grounded_facts
from .io import ensure_layout, load_nodes, write_json, write_text
from .markdown import render_main_document
from .models import SourceRef, WikiPage
from .utils import doc_key_from_node, file_name_from_doc_key, first_sentences, infer_domain, page_id_from_doc_key
from .validator import validate_pages


def _group_nodes_by_source(nodes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        grouped[doc_key_from_node(node)].append(node)
    return grouped


def _guess_source_type(metadata: dict) -> str:
    if metadata.get("is_event") is True:
        return "event"
    return "doc"


def _build_source_page(doc_key: str, doc_nodes: list[dict]) -> WikiPage:
    first_meta = (doc_nodes[0].get("metadata", {}) or {}) if doc_nodes else {}
    file_name = first_meta.get("file_name") or file_name_from_doc_key(doc_key)
    source_type = _guess_source_type(first_meta)
    domain = infer_domain(str(doc_key))
    page_id = page_id_from_doc_key(str(first_meta.get("file_path") or doc_key))
    title = file_name

    texts = [str(n.get("text", "")).strip() for n in doc_nodes if n.get("text")]
    merged_text = "\n".join(texts)
    summary = first_sentences(merged_text)

    source_ref = SourceRef(
        file_path=str(first_meta.get("file_path") or doc_key),
        file_name=file_name,
        source_type=source_type,
        source_url=first_meta.get("source_url"),
        last_modified=first_meta.get("last_modified_date"),
    )

    facts = extract_grounded_facts(merged_text, source_ref=source_ref.file_path)
    contradiction_notes = detect_contradictions(facts)
    context = [t[:240] for t in texts[:5]]
    tags = [domain, source_type]
    source_log = [
        f"doc_key: `{doc_key}`",
        f"access_type: `{first_meta.get('access_type', '')}`",
        f"role: `{first_meta.get('role', '')}`",
        f"organization: `{first_meta.get('organization', '')}`",
        f"user_id: `{first_meta.get('user_id', '')}`",
        f"chunking_method: `{first_meta.get('chunking_method', '')}`",
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
        node_count=len(doc_nodes),
        status="verified" if facts else "draft",
        contradiction_notes=contradiction_notes,
        summary=summary,
        source_log=source_log,
        reference_context=context,
        open_questions=[] if facts else ["No deterministic grounded facts detected yet."],
    )


def _add_simple_cross_refs(pages: list[WikiPage]) -> None:
    by_domain: dict[str, list[WikiPage]] = defaultdict(list)
    for page in pages:
        by_domain[page.domain].append(page)
    for domain_pages in by_domain.values():
        ids = [p.page_id for p in domain_pages]
        for page in domain_pages:
            page.cross_refs = [pid for pid in ids if pid != page.page_id][:8]


def build_wiki(nodes_path: str | Path, output_dir: str | Path = ".") -> dict:
    nodes = load_nodes(nodes_path)
    paths = ensure_layout(output_dir)

    grouped = _group_nodes_by_source(nodes)
    pages = [_build_source_page(doc_key, doc_nodes) for doc_key, doc_nodes in grouped.items()]
    _add_simple_cross_refs(pages)

    graph_payload = {
        "nodes": [{"id": p.page_id, "domain": p.domain, "title": p.title} for p in pages],
        "edges": [
            {"source": p.page_id, "target": target, "relation": "related"}
            for p in pages
            for target in p.cross_refs
        ],
    }
    write_json(paths["graph"] / "graph.json", graph_payload)
    write_text(
        paths["graph"] / "graph.html",
        "<html><body><h1>Graph Placeholder</h1><p>Use graph.json for now.</p></body></html>\n",
    )

    issues = validate_pages(pages)
    main_document = render_main_document(
        pages,
        nodes_path=str(Path(nodes_path)),
        total_nodes=len(nodes),
        output_dir=str(Path(output_dir)),
        issues=issues,
    )
    write_text(paths["wiki"] / "main.md", main_document)
    write_text(
        paths["wiki"] / "validation_report.md",
        "# Validation Report\n\n"
        + ("\n".join(f"- {issue}" for issue in issues) if issues else "- No issues detected.\n"),
    )

    return {
        "total_nodes": len(nodes),
        "total_sources": len(pages),
        "issues": issues,
        "main_document": str(paths["wiki"] / "main.md"),
        "wiki_dir": str(paths["wiki"]),
    }
