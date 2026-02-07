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
    ids = [node.id_ for node in nodes]
    documents = [node.text for node in nodes]
    metadatas = [node.metadata for node in nodes]

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
        return top_k_data

    # Since we will handle every error the same way, we don't need to catch specific exceptions
    except Exception as e:
        print(f"Error in reranking: {e}")
        nodes.sort(key=lambda x: x.score, reverse=True)
        nodes = nodes[: config.reranker_backup_top_n]
        return nodes
