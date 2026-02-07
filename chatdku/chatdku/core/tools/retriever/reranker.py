from typing import Any, Dict

import requests

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import NodeWithScore


def call_vllm_rerank(
    query: str,
    documents: list[str],
) -> list[float]:
    """
    Call vLLM's /v1/rerank endpoint and return the scores in document order.
    Assumes vLLM was started with --task score so that /v1/rerank is available.
    """
    prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'

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

    resp = requests.post(config.reranker_base_url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    results = sorted(data["results"], key=lambda x: x["index"])
    scores = [r["relevance_score"] for r in results]
    return scores


def rerank(
    nodes: list[NodeWithScore],
    query: str,
    reranker_top_n: int,
) -> Dict[str, Any]:
    """
    Filters a list of NodeWithScore to the top-k items based on vLLM reranking scores.

    Args:
        nodes: The raw dictionary returned by the retrievers.
        query: The user query string used for reranking.
        reranker_top_n: The number of top results to keep.

    Returns:
        A filtered dictionary with the same structure as chroma_result,
        containing only the top_k items sorted by relevance score.
    """
    ids = [node.id_ for node in nodes]
    documents = [node.text for node in nodes]
    metadatas = [node.metadata for node in nodes]

    scores = call_vllm_rerank(
        query=query,
        documents=documents,
    )

    # Zip everything together to keep data synchronized during sorting
    combined_data = []
    for i in range(len(ids)):
        combined_data.append(
            {
                "id": ids[i],
                "document": documents[i],
                "metadata": metadatas[i],
                "score": scores[i],
            }
        )

    # Sort by score (descending) and slice top_k
    combined_data.sort(key=lambda x: x["score"], reverse=True)
    top_k_data = combined_data[:reranker_top_n]

    # Reconstruct the retriever result structure
    filtered_result = {
        "ids": [[item["id"] for item in top_k_data]],
        "documents": [[item["document"] for item in top_k_data]],
        "metadatas": [[item["metadata"] for item in top_k_data]],
        # Replacing "distances" with the new relevance scores.
        # NOTE: Chroma distances are usually "lower is better", but rerank scores
        # are "higher is better". Downstream functions must be aware of this.
        "distances": [[item["score"] for item in top_k_data]],
    }
    return filtered_result
