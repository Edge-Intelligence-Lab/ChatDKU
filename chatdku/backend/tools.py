from chatdku.core.tools.llama_index_tools import KeywordRetrieverOuter, VectorRetrieverOuter
from chatdku.core.tools.syllabi_tool.query_curriculum_db import QueryCurriculumOuter


def get_tools(user_id: str, search_mode, docs):

    base_tools = [
        KeywordRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id=user_id,
            search_mode=search_mode,
            files=docs,
        ),
        VectorRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id=user_id,
            search_mode=search_mode,
            files=docs,
        ),
        QueryCurriculumOuter(),
    ]

    return base_tools
