from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .extractors import extract_grounded_facts
from .io import clear_markdown_dir, ensure_layout, load_nodes, write_json, write_text
from .llm import LLMWikiWriter
from .markdown import (
    render_cluster_page,
    render_index,
    render_main_document,
    render_overview,
    render_service_page,
    render_timeline_page,
    render_topic_page,
    render_validation_report,
)
from .models import SourceRef, WikiPage
from .utils import (
    doc_key_from_node,
    file_name_from_doc_key,
    first_sentences,
    infer_domain,
    page_id_from_doc_key,
    slugify,
    title_from_source,
    unique_preserve_order,
)
from .validator import validate_pages


TOPIC_RULES = [
    {
        "id": "academic_advising",
        "title": "Academic Advising",
        "topic_families": ["advising"],
        "audience": ["undergraduate", "faculty_advisor"],
        "keywords": [
            "academic advising",
            "faculty advisor",
            "advising faq",
            "undergraduate advising",
            "advisor manual",
            "pre-health",
            "pre-law",
        ],
        "preferred_surfaces": ["website", "handbook", "faq", "slides", "guide", "other"],
        "service": "academic_advising",
    },
    {
        "id": "majors_overview",
        "title": "Majors and Tracks Overview",
        "topic_families": ["major_track_program"],
        "audience": ["undergraduate"],
        "keywords": ["majors", "tracks", "major convener", "major alignment", "division of"],
        "preferred_surfaces": ["bulletin", "website", "guide", "spreadsheet", "other"],
        "service": "academic_advising",
    },
    {
        "id": "major_declaration",
        "title": "Major Declaration",
        "topic_families": ["major_track_program", "forms_workflows"],
        "audience": ["undergraduate"],
        "keywords": ["major declaration", "declare their majors", "declaring your major"],
        "preferred_surfaces": ["slides", "guide", "website", "bulletin", "other"],
        "service": "academic_advising",
        "timeline": "major_declaration_cycle",
    },
    {
        "id": "registration_planning",
        "title": "Registration and Planning",
        "topic_families": ["registration_planning", "forms_workflows"],
        "audience": ["undergraduate"],
        "keywords": [
            "registration",
            "schedule builder",
            "student self-service center",
            "4-year plan",
            "pre-registration",
            "class search",
        ],
        "preferred_surfaces": ["guide", "slides", "faq", "website", "other"],
        "service": "registrar_student_center",
        "timeline": "registration_cycle",
    },
    {
        "id": "course_substitution",
        "title": "Course Substitution",
        "topic_families": ["registration_planning", "forms_workflows"],
        "audience": ["undergraduate"],
        "keywords": ["course substitution"],
        "preferred_surfaces": ["form", "guide", "website", "other"],
        "service": "academic_advising",
    },
    {
        "id": "leave_of_absence",
        "title": "Leave of Absence",
        "topic_families": ["student_support", "forms_workflows"],
        "audience": ["student", "undergraduate"],
        "keywords": ["leave of absence", "loa"],
        "preferred_surfaces": ["guide", "website", "form", "other"],
        "service": "academic_advising",
    },
    {
        "id": "cr_nc",
        "title": "CR/NC Policy",
        "topic_families": ["academic_policy"],
        "audience": ["undergraduate", "faculty_advisor"],
        "keywords": ["cr/nc", "crnc"],
        "preferred_surfaces": ["faq", "website", "handbook", "other"],
        "service": "academic_advising",
    },
    {
        "id": "overload_policy",
        "title": "Overload Policy",
        "topic_families": ["academic_policy"],
        "audience": ["undergraduate"],
        "keywords": ["overload policy", "overload"],
        "preferred_surfaces": ["guide", "website", "other"],
        "service": "academic_advising",
    },
    {
        "id": "signature_work",
        "title": "Signature Work",
        "topic_families": ["signature_work"],
        "audience": ["undergraduate", "signature_work_student"],
        "keywords": ["signature work", "sw mentor", "signature-work", "mentor information sheet"],
        "preferred_surfaces": ["handbook", "calendar", "form", "website", "other"],
        "service": "signature_work_support",
        "timeline": "signature_work_cycle",
    },
    {
        "id": "student_accessibility",
        "title": "Student Accessibility Service",
        "topic_families": ["student_support", "office_service"],
        "audience": ["student"],
        "keywords": ["student accessibility", "accessibility service"],
        "preferred_surfaces": ["handbook", "website", "other"],
        "service": "student_accessibility",
    },
]

SERVICE_RULES = {
    "academic_advising": {
        "title": "Office of Undergraduate Advising",
        "summary": "Service index for advising-related topics, faculty advisor support, and undergraduate planning materials.",
    },
    "registrar_student_center": {
        "title": "Registrar and Student Self-Service Center",
        "summary": "Service index for registration, planning, and student self-service workflows.",
    },
    "signature_work_support": {
        "title": "Signature Work Support",
        "summary": "Service index for Signature Work handbook, mentoring, and calendar-related materials.",
    },
    "student_accessibility": {
        "title": "Student Accessibility Service",
        "summary": "Service index for accessibility support materials and related student workflows.",
    },
}

TIMELINE_RULES = {
    "major_declaration_cycle": {
        "title": "Major Declaration Timing",
        "summary": "Timeline index for when students usually encounter major declaration materials and related advising guidance.",
    },
    "registration_cycle": {
        "title": "Registration Cycle",
        "summary": "Timeline index for planning and registration materials across the term cycle.",
    },
    "signature_work_cycle": {
        "title": "Signature Work Cycle",
        "summary": "Timeline index for Signature Work handbook and calendar materials across the academic year.",
    },
}

SURFACE_PRIORITY = {
    "bulletin": 0,
    "handbook": 1,
    "website": 2,
    "guide": 3,
    "faq": 4,
    "form": 5,
    "calendar": 6,
    "slides": 7,
    "spreadsheet": 8,
    "other": 9,
}


def _group_nodes_by_source(nodes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        grouped[doc_key_from_node(node)].append(node)
    return grouped


def _detect_surface(file_path: str, file_name: str) -> str:
    lower = f"{file_path} {file_name}".lower()
    if "bulletin" in lower:
        return "bulletin"
    if "handbook" in lower or "manual" in lower:
        return "handbook"
    if "faq" in lower:
        return "faq"
    if "form" in lower:
        return "form"
    if "guide" in lower:
        return "guide"
    if "calendar" in lower:
        return "calendar"
    if file_path.endswith(".pptx"):
        return "slides"
    if file_path.endswith(".xlsx"):
        return "spreadsheet"
    if "dukekunshan.edu.cn" in lower or file_path.endswith(".html"):
        return "website"
    return "other"


def _classify_topic(source: dict) -> dict:
    title_haystack = " ".join(
        [
            source["title"].lower(),
            source["file_name"].lower(),
            source["file_path"].lower(),
        ]
    )
    summary_haystack = source["summary"].lower()
    best_rule = None
    best_score = -1
    for rule in TOPIC_RULES:
        title_hits = sum(1 for keyword in rule["keywords"] if keyword in title_haystack)
        summary_hits = sum(1 for keyword in rule["keywords"] if keyword in summary_haystack)
        if source["surface"] == "website" and title_hits == 0:
            score = 0
        elif title_hits == 0 and summary_hits < 2:
            score = 0
        else:
            score = title_hits * 3 + summary_hits
        if score > best_score:
            best_score = score
            best_rule = rule
    if best_rule and best_score > 0:
        return best_rule
    return {
        "id": f"general_{slugify(source['domain'])}",
        "title": f"{source['domain'].replace('-', ' ').title()} Reference",
        "topic_families": ["reference_catalog"],
        "audience": ["student"],
        "keywords": [],
        "service": None,
    }


def _build_source_record(doc_key: str, doc_nodes: list[dict]) -> dict:
    first_meta = (doc_nodes[0].get("metadata", {}) or {}) if doc_nodes else {}
    texts = [str(node.get("text", "")).strip() for node in doc_nodes if node.get("text")]
    merged_text = "\n".join(texts)
    file_name = first_meta.get("file_name") or file_name_from_doc_key(doc_key)
    file_path = str(first_meta.get("file_path") or doc_key)
    title = title_from_source(file_name, merged_text, file_path)
    summary = first_sentences(merged_text)
    surface = _detect_surface(file_path, file_name)
    topic_rule = _classify_topic(
        {
            "title": title,
            "file_name": file_name,
            "file_path": file_path,
            "summary": summary,
            "domain": infer_domain(file_path),
            "surface": surface,
        }
    )
    source_ref = SourceRef(
        file_path=file_path,
        file_name=file_name,
        source_type=surface,
        source_url=first_meta.get("source_url") or first_meta.get("event_url"),
        last_modified=first_meta.get("last_modified_date"),
    )
    return {
        "doc_key": doc_key,
        "page_id": page_id_from_doc_key(file_path),
        "title": title,
        "file_name": file_name,
        "file_path": file_path,
        "domain": infer_domain(file_path),
        "summary": summary,
        "surface": surface,
        "node_count": len(doc_nodes),
        "source_ref": source_ref,
        "facts": extract_grounded_facts(merged_text, source_ref=file_path),
        "reference_context": [text[:240] for text in texts[:3]],
        "topic_rule": topic_rule,
    }


def _preferred_sources(records: list[dict], limit: int = 3) -> list[str]:
    topic_rule = records[0]["topic_rule"]
    preferred_surfaces = topic_rule.get("preferred_surfaces", [])
    preferred_rank = {surface: idx for idx, surface in enumerate(preferred_surfaces)}
    ordered = sorted(
        records,
        key=lambda item: (
            preferred_rank.get(item["surface"], 100),
            SURFACE_PRIORITY.get(item["surface"], SURFACE_PRIORITY["other"]),
            item["file_name"].lower(),
        ),
    )
    return [record["file_path"] for record in ordered[:limit]]


def _build_cluster_pages(source_records: list[dict]) -> list[WikiPage]:
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for record in source_records:
        by_topic[record["topic_rule"]["id"]].append(record)

    cluster_pages: list[WikiPage] = []
    for topic_id, records in sorted(by_topic.items()):
        topic_rule = records[0]["topic_rule"]
        surfaces = unique_preserve_order([record["surface"] for record in records])
        preferred_rank = {
            surface: idx for idx, surface in enumerate(topic_rule.get("preferred_surfaces", []))
        }
        authority_order = sorted(
            surfaces,
            key=lambda item: (preferred_rank.get(item, 100), SURFACE_PRIORITY.get(item, 99)),
        )
        cluster_status = "stable"
        if len(records) >= 4 and len(surfaces) >= 3:
            cluster_status = "mixed"
        summary = (
            f"Source cluster for {topic_rule['title']} with {len(records)} overlapping source(s) "
            f"across {', '.join(surfaces)}."
        )
        cluster_pages.append(
            WikiPage(
                page_id=f"cluster.{topic_id}",
                title=f"{topic_rule['title']} Source Cluster",
                page_type="source_cluster",
                domain=records[0]["domain"],
                tags=surfaces + topic_rule["topic_families"],
                source_refs=[record["source_ref"] for record in records],
                ground_truth_refs=[],
                cross_refs=[],
                output_path=f"clusters/{slugify(topic_id)}.md",
                topic_families=topic_rule["topic_families"],
                audience=topic_rule["audience"],
                source_surfaces=surfaces,
                preferred_detail_sources=_preferred_sources(records),
                node_count=sum(record["node_count"] for record in records),
                status="active",
                cluster_status=cluster_status,
                summary=summary,
                source_log=authority_order,
                reference_context=[],
            )
        )
    return cluster_pages


def _build_topic_pages(cluster_pages: list[WikiPage]) -> list[WikiPage]:
    topic_pages: list[WikiPage] = []
    for cluster in cluster_pages:
        topic_id = cluster.page_id.removeprefix("cluster.")
        title = cluster.title.removesuffix(" Source Cluster")
        quick_orientation = [
            f"topic_family: {', '.join(cluster.topic_families)}",
            f"source_surfaces: {', '.join(cluster.source_surfaces)}",
            f"source_count: {len(cluster.source_refs)}",
            f"best_open_first: {Path(cluster.preferred_detail_sources[0]).name if cluster.preferred_detail_sources else 'N/A'}",
        ]
        topic_pages.append(
            WikiPage(
                page_id=f"topic.{topic_id}",
                title=title,
                page_type="topic_index",
                domain=cluster.domain,
                tags=cluster.topic_families + ["topic_index"],
                source_refs=cluster.source_refs,
                ground_truth_refs=[],
                cross_refs=[cluster.page_id],
                output_path=f"topics/{slugify(topic_id)}.md",
                topic_families=cluster.topic_families,
                audience=cluster.audience,
                source_surfaces=cluster.source_surfaces,
                canonical_source_cluster=cluster.page_id,
                preferred_detail_sources=cluster.preferred_detail_sources,
                status="active",
                cluster_status=cluster.cluster_status,
                summary=(
                    f"General DKU topic index for {title.lower()}. "
                    f"Start here, then open the best detailed source if needed."
                ),
                reference_context=quick_orientation,
            )
        )
    return topic_pages


def _sample_cluster_sources(cluster: WikiPage, limit: int = 6) -> list[dict]:
    samples: list[dict] = []
    for ref in cluster.source_refs[:limit]:
        samples.append(
            {
                "file_name": ref.file_name,
                "file_path": ref.file_path,
                "source_type": ref.source_type,
                "last_modified": ref.last_modified,
            }
        )
    return samples


def _apply_llm_summaries(
    cluster_pages: list[WikiPage],
    topic_pages: list[WikiPage],
) -> None:
    writer = LLMWikiWriter()
    cluster_by_id = {page.page_id: page for page in cluster_pages}

    for cluster in cluster_pages:
        try:
            cluster.summary = writer.write_cluster_summary(
                cluster_title=cluster.title,
                topic_families=cluster.topic_families,
                sources=_sample_cluster_sources(cluster),
            )
        except Exception:
            pass

    for topic in topic_pages:
        cluster = cluster_by_id.get(topic.canonical_source_cluster or "")
        try:
            topic.summary = writer.write_topic_summary(
                topic_title=topic.title,
                topic_families=topic.topic_families,
                cluster_status=topic.cluster_status,
                preferred_sources=topic.preferred_detail_sources,
            )
        except Exception:
            pass
        if cluster:
            topic.reference_context = [
                f"topic_family: {', '.join(topic.topic_families)}",
                f"source_surfaces: {', '.join(cluster.source_surfaces)}",
                f"source_count: {len(cluster.source_refs)}",
                f"best_open_first: {Path(topic.preferred_detail_sources[0]).name if topic.preferred_detail_sources else 'N/A'}",
            ]


def _build_service_pages(topic_pages: list[WikiPage]) -> list[WikiPage]:
    by_service: dict[str, list[WikiPage]] = defaultdict(list)
    topic_rule_by_page_id = {f"topic.{rule['id']}": rule for rule in TOPIC_RULES}
    for page in topic_pages:
        rule = topic_rule_by_page_id.get(page.page_id)
        if rule and rule.get("service"):
            by_service[rule["service"]].append(page)

    pages: list[WikiPage] = []
    for service_id, topic_refs in sorted(by_service.items()):
        meta = SERVICE_RULES[service_id]
        pages.append(
            WikiPage(
                page_id=f"service.{service_id}",
                title=meta["title"],
                page_type="service_index",
                domain="general",
                tags=["office_service"],
                source_refs=[ref for page in topic_refs for ref in page.source_refs[:1]],
                ground_truth_refs=[],
                cross_refs=[page.page_id for page in topic_refs],
                output_path=f"services/{slugify(service_id)}.md",
                topic_families=["office_service"],
                audience=["student"],
                source_surfaces=unique_preserve_order(
                    [surface for page in topic_refs for surface in page.source_surfaces]
                ),
                preferred_detail_sources=unique_preserve_order(
                    [src for page in topic_refs for src in page.preferred_detail_sources]
                )[:3],
                status="active",
                summary=meta["summary"],
                reference_context=[page.title for page in topic_refs[:6]],
            )
        )
    return pages


def _build_timeline_pages(topic_pages: list[WikiPage]) -> list[WikiPage]:
    by_timeline: dict[str, list[WikiPage]] = defaultdict(list)
    topic_rule_by_page_id = {f"topic.{rule['id']}": rule for rule in TOPIC_RULES}
    for page in topic_pages:
        rule = topic_rule_by_page_id.get(page.page_id)
        if rule and rule.get("timeline"):
            by_timeline[rule["timeline"]].append(page)

    pages: list[WikiPage] = []
    for timeline_id, topic_refs in sorted(by_timeline.items()):
        meta = TIMELINE_RULES[timeline_id]
        pages.append(
            WikiPage(
                page_id=f"timeline.{timeline_id}",
                title=meta["title"],
                page_type="timeline_index",
                domain="general",
                tags=["timeline_index"],
                source_refs=[ref for page in topic_refs for ref in page.source_refs[:1]],
                ground_truth_refs=[],
                cross_refs=[page.page_id for page in topic_refs],
                output_path=f"timelines/{slugify(timeline_id)}.md",
                topic_families=unique_preserve_order(
                    [family for page in topic_refs for family in page.topic_families]
                ),
                audience=["student"],
                source_surfaces=unique_preserve_order(
                    [surface for page in topic_refs for surface in page.source_surfaces]
                ),
                preferred_detail_sources=unique_preserve_order(
                    [src for page in topic_refs for src in page.preferred_detail_sources]
                )[:3],
                status="active",
                summary=meta["summary"],
            )
        )
    return pages


def _attach_related_pages(
    topic_pages: list[WikiPage],
    cluster_pages: list[WikiPage],
    service_pages: list[WikiPage],
    timeline_pages: list[WikiPage],
) -> None:
    cluster_by_topic = {
        cluster.page_id.removeprefix("cluster."): cluster.page_id for cluster in cluster_pages
    }
    for page in topic_pages:
        topic_key = page.page_id.removeprefix("topic.")
        related = [cluster_by_topic.get(topic_key)]
        for other in topic_pages:
            if other.page_id == page.page_id:
                continue
            if set(other.topic_families) & set(page.topic_families):
                related.append(other.page_id)
        for service in service_pages:
            if page.page_id in service.cross_refs:
                related.append(service.page_id)
        for timeline in timeline_pages:
            if page.page_id in timeline.cross_refs:
                related.append(timeline.page_id)
        page.cross_refs = [ref for ref in unique_preserve_order([item for item in related if item]) if ref != page.page_id][:8]

    for cluster in cluster_pages:
        topic_ref = f"topic.{cluster.page_id.removeprefix('cluster.')}"
        cluster.cross_refs = [topic_ref] if topic_ref in {page.page_id for page in topic_pages} else []


def build_wiki(
    nodes_path: str | Path,
    output_dir: str | Path = ".",
    *,
    use_llm: bool = False,
) -> dict:
    nodes = load_nodes(nodes_path)
    paths = ensure_layout(output_dir)
    for key in ["topics", "clusters", "services", "timelines"]:
        clear_markdown_dir(paths[key])

    grouped = _group_nodes_by_source(nodes)
    source_records = [_build_source_record(doc_key, doc_nodes) for doc_key, doc_nodes in grouped.items()]

    cluster_pages = _build_cluster_pages(source_records)
    topic_pages = _build_topic_pages(cluster_pages)
    service_pages = _build_service_pages(topic_pages)
    timeline_pages = _build_timeline_pages(topic_pages)
    _attach_related_pages(topic_pages, cluster_pages, service_pages, timeline_pages)

    if use_llm:
        _apply_llm_summaries(cluster_pages, topic_pages)

    all_pages = topic_pages + cluster_pages + service_pages + timeline_pages
    pages_by_id = {page.page_id: page for page in all_pages}

    for page in topic_pages:
        write_text(paths["wiki"] / page.output_path, render_topic_page(page, pages_by_id))
    for page in cluster_pages:
        write_text(paths["wiki"] / page.output_path, render_cluster_page(page, pages_by_id))
    for page in service_pages:
        write_text(paths["wiki"] / page.output_path, render_service_page(page, pages_by_id))
    for page in timeline_pages:
        write_text(paths["wiki"] / page.output_path, render_timeline_page(page, pages_by_id))

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
            "topic_family": page.topic_families,
            "output_path": page.output_path,
            "source_count": len(page.source_refs),
            "cross_ref_count": len(page.cross_refs),
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
        "total_topics": len(topic_pages),
        "total_clusters": len(cluster_pages),
        "total_services": len(service_pages),
        "total_timelines": len(timeline_pages),
        "issues": issues,
        "index_document": str(paths["wiki"] / "index.md"),
        "main_document": str(paths["wiki"] / "main.md"),
        "wiki_dir": str(paths["wiki"]),
    }
