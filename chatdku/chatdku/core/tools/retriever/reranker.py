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
    prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'  # noqa: E501

    suffix = "<|im_end|>\n<|im_start|>assistant\n"

    query_template = "{prefix}<Instruct>: {instruction}\n<Query>: {query}\n"

    document_template = "<Document>: {doc}{suffix}"

    instruction = (
        "Given a search query, retrieve relevant candidates that answer the query."
    )

    documents = [document_template.format(doc=doc, suffix=suffix) for doc in documents]

    payload = {
        "query": query_template.format(
            prefix=prefix, instruction=instruction, query=query
        ),
        "documents": documents,
    }

    headers = {"Content-Type": "application/json"}
    if config.reranker_api_key:
        headers["Authorization"] = f"Bearer {config.reranker_api_key}"

    # Sending the payload to the reranker and getting a response
    # This is a sync function. Could Make it async in the future.
    resp = requests.post(
        config.reranker_base_url + "/v1/rerank", headers=headers, json=payload
    )
    data = resp.json()
    results = sorted(data["results"], key=lambda x: x["index"])
    scores = [r["relevance_score"] for r in results]
    return scores


def rerank(
    nodes: list[NodeWithScore],
    query: str,
    reranker_top_n: int,
) -> list[NodeWithScore]:
    """
    Filters a list of NodeWithScore to the top-k items based on vLLM reranking scores.

    Args:
        nodes: The raw dictionary returned by the retrievers.
        query: The user query string used for reranking.
        reranker_top_n: The number of top results to keep.

    Returns:
        A filtered list of NodeWithScore containing only the top_k
        items sorted by relevance score.
    """
    ids = [node.node_id for node in nodes]
    documents = [node.text for node in nodes]
    metadatas = [node.metadata for node in nodes]
    # Phoenix Tracing
    with (
        config.tracer.start_as_current_span("Reranker")
        if hasattr(config, "tracer")
        else nullcontext()
    ) as span:
        span.set_attributes(
            {
                SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                # NOTE: Should we also add the documents in the input?
                SpanAttributes.INPUT_VALUE: safe_json_dumps(
                    dict(
                        query=query,
                        reranker_top_n=reranker_top_n,
                    )
                ),
                SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
            }
        )

        try:
            scores = call_vllm_rerank(
                query=query,
                documents=documents,
            )
            # Zip everything together to keep data synchronized during sorting
            combined_data = []
            for i in range(len(ids)):
                combined_data.append(
                    NodeWithScore(
                        node_id=ids[i],
                        text=documents[i],
                        metadata=metadatas[i],
                        score=scores[i],
                    )
                )

            # Sort by score (descending) and slice top_k
            combined_data.sort(key=lambda x: x.score, reverse=True)
            top_k_data = combined_data[:reranker_top_n]

            # Send the results to Phoenix
            span.set_attributes(nodes_to_OTLP(top_k_data))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(result=top_k_data)
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
            return top_k_data

        # Since we will handle every error the same way, we don't need to catch specific exceptions
        except Exception as e:
            print(f"Error in reranking: {e}")
            nodes.sort(key=lambda x: x.score, reverse=True)
            nodes = nodes[: config.reranker_backup_top_n]

            span.record_exception(e)
            # Send the error and the backup nodes to Phoenix
            span.set_attributes(nodes_to_OTLP(nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(
                            result=nodes,
                        )
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.ERROR))
            return nodes
