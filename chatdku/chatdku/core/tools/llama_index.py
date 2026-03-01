import logging

from opentelemetry.trace import get_current_span

from chatdku.core.tools.retriever.base_retriever import NodeWithScore
from chatdku.core.tools.retriever.keyword_retriever import KeywordRetriever
from chatdku.core.tools.retriever.reranker import rerank
from chatdku.core.tools.retriever.vector_retriever import VectorRetriever
from chatdku.core.tools.utils import QueryTimeoutError, timeout

logger = logging.getLogger(__name__)


def nodes_to_dicts(nodes: list[NodeWithScore]) -> list:
    result = []
    for node in nodes:
        if isinstance(node, NodeWithScore):
            result.append([{"text": node.text, "metadata": node.metadata}])
        if isinstance(node, str):
            result.append(node)
    return result


def VectorRetrieverOuter(
    retriever_top_k: int = 25,
    use_reranker: bool = True,
    reranker_top_n: int = 5,
    user_id: str = "Chat_DKU",
    search_mode: int = 0,
    files: list = [],
):
    """
    Retrieve reranked relevant documents using semantic search.

    Args:
        user_id: If set anything other than Chat_DKU, means the net_id of the user
        search_mode: 0 for searching  the default corpus | 1 for searching the user
            corpus | 2 for searching both
        docs: Names of documents searching. Required for search_mode 1 or 2.

    """
    if not (0 <= search_mode <= 2):
        logger.warning(
            f"Invalid search_mode: {search_mode}. Must be between 0 and 2."
            " Defaulting to 0."
        )
        search_mode = 0

    if search_mode != 0 and not files:
        logger.warning("`docs` must be provided when search_mode is 1 or 2.")
        search_mode = 0
        files = []

    vector_retriever = VectorRetriever(
        retriever_top_k=retriever_top_k,
        user_id=user_id,
        search_mode=search_mode,
        files=files,
    )

    # Had to name this differently from VectorRetriever
    def VectorQuery(
        semantic_query: str,
    ) -> list:
        """
        Retrieve reranked relevant documents using semantic search.

        Combines vector similarity search with reranking to find the most
        relevant documents. Use VectorRetriever for conceptual searches.

        Args:
            semantic_query (str): Natural language query for semantic/conceptual search

        Returns:
            matched_documents_list
        """
        parent_span = get_current_span()
        vector_result = []
        # Retrieve documents with individual error handling
        try:
            with timeout() as ctx:
                vector_result = ctx.run(
                    vector_retriever.query_with_tell,
                    query=semantic_query,
                    parent_span=parent_span,
                )
            if use_reranker:
                vector_result = rerank(vector_result, semantic_query, reranker_top_n)
        except ValueError as e:
            raise e
        except QueryTimeoutError as e:
            raise Exception(f"{e}: Vector retriever timed out.")
        except Exception as e:
            raise Exception(f"Vector retrieval failed: {e}")

        overall_dicts = nodes_to_dicts(vector_result)
        return overall_dicts

    return VectorQuery


def KeywordRetrieverOuter(
    retriever_top_k: int = 25,
    use_reranker: bool = True,
    reranker_top_n: int = 5,
    user_id: str = "Chat_DKU",
    search_mode: int = 0,
    files: list = [],
):
    """
    Retrieve relevant documents using BM25 keyword matching.

    Args:
        user_id: If set anything other than Chat_DKU, means the net_id of the user
        search_mode: 0 for searching  the default corpus | 1 for searching the user
            corpus | 2 for searching both
        docs: Names of documents searching. Required for search_mode 1 or 2.

    """
    if not (0 <= search_mode <= 2):
        logger.warning(
            f"Invalid search_mode: {search_mode}. Must be between 0 and 2."
            " Defaulting to 0."
        )
        search_mode = 0

    if search_mode != 0 and not files:
        logger.warning("`docs` must be provided when search_mode is 1 or 2.")
        search_mode = 0
        files = []

    keyword_retriever = KeywordRetriever(
        retriever_top_k=retriever_top_k,
        user_id=user_id,
        search_mode=search_mode,
        files=files,
    )

    def KeywordQuery(
        keyword_query: str | list[str],
    ) -> list:
        """
        Retrieve relevant documents using BM25 keyword matching.

        Combines BM25 keyword search with reranker to find the most
        relevant documents. Use KeywordRetriever for exact term matching.

        Args:
            keyword_query (str | list[str]): Specific terms or phrases for BM25 keyword matching.

        Returns:
            matched_documents_list
        """
        parent_span = get_current_span()
        if isinstance(keyword_query, list):
            for i in range(len(keyword_query)):
                keyword_query[i] = str(keyword_query[i])

        keyword_result = []

        try:
            with timeout() as ctx:
                keyword_result = ctx.run(
                    keyword_retriever.query_with_tell,
                    query=keyword_query,
                    parent_span=parent_span,
                )
            if use_reranker:
                keyword_result = rerank(
                    keyword_result, str(keyword_query), reranker_top_n
                )
        except QueryTimeoutError as e:
            raise Exception(f"Keyword retriever timeout: {e}")
        except Exception as e:
            raise Exception(f"Keyword retrieval failed: {e}")

        overall_dict = nodes_to_dicts(keyword_result)
        return overall_dict

    return KeywordQuery
