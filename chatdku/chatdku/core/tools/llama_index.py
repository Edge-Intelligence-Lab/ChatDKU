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


def VectorRetrieverOuter(
    internal_memory: dict,
    retriever_top_k: int = 25,
    use_reranker: bool = True,
    reranker_top_n: int = 5,
):
    vector_retriever = VectorRetriever(
        internal_memory,
        retriever_top_k,
    )

    def VectorRetriever(
        semantic_query: str,
    ) -> tuple[list, dict]:
        """
        Retrieve reranked relevant documents using semantic search.

        Combines vector similarity search with reranking to find the most
        relevant documents. Use VectorRetriever for conceptual searches.

        Args:
            semantic_query (str): Natural language query for semantic/conceptual search

        Returns:
            Tuple of (matched_documents_list, internal_result_dict)
        """
        vector_result = []
        # Retrieve documents with individual error handling
        try:
            with timeout() as ctx:
                vector_result = ctx.run(
                    vector_retriever.query_with_tell, query=semantic_query
                )
            if use_reranker:
                vector_result = rerank(vector_result, semantic_query, reranker_top_n)
        except ValueError as e:
            raise e
        except QueryTimeoutError as e:
            raise e("Vector retriever timed out.")
        except Exception as e:
            raise Exception(f"Vector retrieval failed: {e}")

        overall_dicts = nodes_to_dicts(vector_result)
        internal_result = {
            "ids": {
                node.node_id
                for node in vector_result
                if isinstance(node, NodeWithScore)
            }
        }
        return overall_dicts, internal_result

    return VectorRetriever


def KeywordRetrieverOuter(
    internal_memory: dict,
    retriever_top_k: int = 25,
    use_reranker: bool = True,
    reranker_top_n: int = 5,
):
    keyword_retriever = KeywordRetriever(
        internal_memory,
        retriever_top_k,
    )

    def KeywordRetriever(
        keyword_query: str | list[str],
    ) -> tuple[list, dict]:
        """
        Retrieve relevant documents using BM25 keyword matching.

        Combines BM25 keyword search with reranker to find the most
        relevant documents. Use KeywordRetriever for exact term matching.

        Args:
            keyword_query (str | list[str]): Specific terms or phrases for BM25 keyword matching.

        Returns:
            Tuple of (matched_documents_list, internal_result_dict)
        """
        if isinstance(keyword_query, list):
            for i in range(len(keyword_query)):
                keyword_query[i] = str(keyword_query[i])

        keyword_result = []

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
            raise e("Keyword retriever timeout.")
        except Exception as e:
            raise Exception(f"Keyword retrieval failed: {e}")

        overall_dict = nodes_to_dicts(keyword_result)
        internal_result = {
            "ids": {
                node.node_id
                for node in keyword_result
                if isinstance(node, NodeWithScore)
            }
        }
        return overall_dict, internal_result

    return KeywordRetriever
