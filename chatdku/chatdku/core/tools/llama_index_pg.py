from contextlib import suppress
from time import perf_counter
import traceback
import uuid

from chatdku.core.tools.retriever.base_retriever import NodeWithScore
from chatdku.core.tools.retriever.reranker import rerank
from chatdku.core.tools.utils import QueryTimeoutError, timeout
from chatdku.core.tools.retriever.postgres_retriever import PostgresRetriever
from chatdku.config import config


def nodes_to_dicts(nodes: list[NodeWithScore]) -> list:
    result = []
    for node in nodes:
        if isinstance(node, NodeWithScore):
            # NOTE: keep existing output shape for interface compatibility
            result.append([{"text": node.text, "metadata": node.metadata}])
        if isinstance(node, str):
            result.append(node)
    return result


def DocRetrieverOuter(
    retriever_top_k: int = 25,
    use_reranker: bool = True,
    reranker_top_n: int = 10,
    user_id: str = "Chat_DKU",
    search_mode: int = 0,
    files: list | None = None,
):
    # Keep this call keyword-based so it stays compatible if the retriever's
    # signature evolves (we've recently added permission + partition args).
    vector_retriever = PostgresRetriever(
        retriever_top_k=retriever_top_k,
        user_id=user_id,
        search_mode=search_mode,
        files=files,
    )

    def DocumentRetriever(
        semantic_query: str,
    ) -> tuple[list, dict]:
        try:
            vector_result: list = []

            try:
                # Fixed budgets (do not rely on config having timeout fields)
                overall_timeout_s = 10.0
                rid = uuid.uuid4().hex[:8]
                tagged_query = f"[rid={rid}] {semantic_query}"

                reranker_guard_s = 0.35
                reranker_cap_s = 2.0

                t0 = perf_counter()
                vector_result = vector_retriever.query_with_tell(query=tagged_query)

                elapsed = perf_counter() - t0

                # If retriever already returned an error payload, don't rerank
                if use_reranker and vector_result and all(
                    isinstance(x, NodeWithScore) for x in vector_result
                ):
                    remaining = overall_timeout_s - elapsed
                    # Only rerank if we have enough time left
                    if remaining > (reranker_guard_s + 0.2):
                        # Temporarily cap reranker timeout based on remaining budget.
                        # (Keep interface stable; don't assume config has reranker_timeout_s.)
                        prev = getattr(config, "reranker_timeout_s", None)
                        try:
                            setattr(
                                config,
                                "reranker_timeout_s",
                                max(
                                    0.2,
                                    min(reranker_cap_s, remaining - reranker_guard_s),
                                ),
                            )
                            vector_result = rerank(
                                vector_result, semantic_query, reranker_top_n
                            )
                        finally:
                            # restore if it existed
                            if prev is None:
                                # best-effort: don't blow up if config is frozen
                                try:
                                    delattr(config, "reranker_timeout_s")
                                except Exception:
                                    pass
                            else:
                                with suppress(Exception):
                                    setattr(config, "reranker_timeout_s", prev)
                    # else: skip rerank (degrade gracefully)

            except ValueError as e:
                vector_result.append(f"semantic_query had an input error: {e}")
            except QueryTimeoutError as e:
                vector_result.append(f"Vector retriever timeout: {e}")
            except Exception as e:
                vector_result.append(
                    "Vector retrieval failed: "
                    + "".join(traceback.format_exception(type(e), e, e.__traceback__))
                )
            overall_result = nodes_to_dicts(vector_result)
            internal_result = {
                "ids": {
                    node.node_id
                    for node in vector_result
                    if isinstance(node, NodeWithScore)
                }
            }
            return overall_result, internal_result

        except Exception as e:
            return [f"Unexpected error: {e}"], {}

    return DocumentRetriever