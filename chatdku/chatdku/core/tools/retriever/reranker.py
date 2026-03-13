from contextlib import nullcontext

import requests
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import NodeWithScore, nodes_to_OTLP


def call_vllm_rerank(
    query: str,
    documents: list[str],
) -> list[float]:
    """
    Call vLLM's /v1/rerank endpoint and return the scores in document order.
    Assumes vLLM was started with --task score so that /v1/rerank is available.
    """
    if not documents:
        return []

    prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'  # noqa: E501
    suffix = "<|im_end|>\n<|im_start|>assistant\n"
    query_template = "{prefix}<Instruct>: {instruction}\n<Query>: {query}\n"
    document_template = "<Document>: {doc}{suffix}"
    instruction = "Given a search query, retrieve relevant candidates that answer the query."

    documents = [document_template.format(doc=doc, suffix=suffix) for doc in documents]
    query = query_template.format(prefix=prefix, instruction=instruction, query=query)

    payload = {
        "model": config.reranker_model,
        "text_pairs": [[query, doc] for doc in documents],
    }

    headers = {"Content-Type": "application/json"}
    if config.reranker_api_key:
        headers["Authorization"] = f"Bearer {config.reranker_api_key}"

    # Fixed timeout values (do not rely on config having timeout fields)
    resp = requests.post(
        config.reranker_base_url + "/v1/rerank",
        headers=headers,
        json=payload,
        timeout=(1.0, 2.5),  # (connect_timeout, read_timeout)
    )
    resp.raise_for_status()

    data = resp.json()
    results = sorted(data["data"], key=lambda x: x["index"])
    scores = [r["relevance_score"] for r in results]
    return scores


def rerank(
    nodes: list[NodeWithScore],
    query: str,
    reranker_top_n: int,
) -> list[NodeWithScore]:
    """
    Filters a list of NodeWithScore to the top-k items based on vLLM reranking scores.
    Interface must remain stable.
    """
    documents = [node.text for node in nodes]

    # Phoenix Tracing (guard against tracer/span being None or non-standard objects)
    tracer = getattr(config, "tracer", None)
    span_cm = tracer.start_as_current_span("Reranker") if tracer else nullcontext()

    with span_cm as span:
        try:
            # Only call span methods if they exist (prevents NoneType/set_attributes crashes)
            if hasattr(span, "set_attributes"):
                span.set_attributes(
                    {
                        SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                        SpanAttributes.INPUT_VALUE: safe_json_dumps(
                            dict(query=query, reranker_top_n=reranker_top_n)
                        ),
                        SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )

            scores = call_vllm_rerank(query=query, documents=documents)

            combined_data: list[NodeWithScore] = []
            for node, score in zip(nodes, scores):
                combined_data.append(
                    NodeWithScore(
                        node_id=node.node_id,
                        text=node.text,
                        metadata=node.metadata,
                        score=score,
                    )
                )

            combined_data.sort(key=lambda x: x.score, reverse=True)
            top_k_data = combined_data[:reranker_top_n]

            if hasattr(span, "set_attributes"):
                span.set_attributes(nodes_to_OTLP(top_k_data))
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(result=top_k_data)),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
            if hasattr(span, "set_status"):
                span.set_status(Status(StatusCode.OK))

            return top_k_data

        except Exception as e:
            # Best-effort fallback: keep interface stable and never raise from reranker
            nodes.sort(key=lambda x: x.score, reverse=True)
            nodes = nodes[: config.reranker_backup_top_n]

            if hasattr(span, "record_exception"):
                span.record_exception(e)
            if hasattr(span, "set_attributes"):
                span.set_attributes(nodes_to_OTLP(nodes))
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(result=nodes)),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
            if hasattr(span, "set_status"):
                span.set_status(Status(StatusCode.ERROR))

            return nodes