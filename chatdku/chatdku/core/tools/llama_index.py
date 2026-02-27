from chatdku.core.tools.retriever.base_retriever import NodeWithScore
from chatdku.core.tools.retriever.keyword_retriever import KeywordRetriever
from chatdku.core.tools.retriever.reranker import rerank
from chatdku.core.tools.retriever.vector_retriever import VectorRetriever
from chatdku.core.tools.utils import QueryTimeoutError, timeout


def nodes_to_dicts(nodes: list[NodeWithScore]) -> list:
    result = []
    for node in nodes:
        if isinstance(node, NodeWithScore):
            result.append([{"text": node.text, "metadata": node.metadata}])
        if isinstance(node, str):
            result.append(node)
    return result


def DocRetrieverOuter(
    internal_memory: dict,
    retriever_top_k: int = 25,
    use_reranker: bool = True,
    reranker_top_n: int = 5,
    user_id: str = "Chat_DKU",
    search_mode: int = 0,
    files: list | None = None,
):
    vector_retriever = VectorRetriever(
        internal_memory,
        retriever_top_k,
        user_id,
        search_mode,
        files,
    )
    keyword_retriever = KeywordRetriever(
        internal_memory,
        retriever_top_k,
        user_id,
        search_mode,
        files,
    )

    def DocumentRetriever(
        semantic_query: str,
        keyword_query: str = "",
    ) -> tuple[list, dict]:
        """
        Retrieve relevant documents using hybrid search (semantic + keyword matching).

        Combines vector similarity search with BM25 keyword ranking to find the most
        relevant documents. Use semantic_query for conceptual searches and keyword_query
        for exact term matching.

        Args:
            semantic_query (str): Natural language query for semantic/conceptual search
            keyword_query (Optional(str)): Specific terms or phrases for BM25 keyword matching.
                This is optional and can be left empty.

        Returns:
            Tuple of (matched_documents_list, internal_result_dict)
            Returns ([], {}) if query times out or fails
        """
        try:
            if isinstance(keyword_query, list):
                for i in range(len(keyword_query)):
                    keyword_query[i] = str(keyword_query[i])

            vector_result = []
            keyword_result = []

            # Retrieve documents with individual error handling
            try:
                with timeout() as ctx:
                    vector_result = ctx.run(
                        vector_retriever.query_with_tell, query=semantic_query
                    )
                    if use_reranker:
                        vector_result = rerank(
                            vector_result, semantic_query, reranker_top_n
                        )
            except ValueError as e:
                vector_result.append(f"semantic_query had an input error: {e}")
            except QueryTimeoutError as e:
                vector_result.append(f"Vector retriever timeout: {e}")
            except Exception as e:
                vector_result.append(f"Vector retrieval failed: {e}")

            if keyword_query:
                try:
                    with timeout() as ctx:
                        keyword_result = ctx.run(
                            keyword_retriever.query_with_tell, query=keyword_query
                        )
                        if use_reranker:
                            keyword_result = rerank(
                                keyword_result, str(keyword_query), reranker_top_n
                            )
                except QueryTimeoutError as e:
                    keyword_result.append(f"Keyword retriever timeout: {e}")
                except Exception as e:
                    keyword_result.append(f"Keyword retrieval failed: {e}")

            total = vector_result + keyword_result
            overall_result = nodes_to_dicts(total)
            internal_result = {
                "ids": {
                    node.node_id for node in total if isinstance(node, NodeWithScore)
                }
            }
            return overall_result, internal_result
        except Exception as e:
            return [f"Unexpected error: {e}"], {}

    return DocumentRetriever
