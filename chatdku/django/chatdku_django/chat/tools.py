from chatdku.core.tools.llama_index_tools import (
    KeywordRetrieverOuter,
    VectorRetrieverOuter,
)
from chatdku.core.tools.syllabi.syllabi_tool import SyllabusLookupOuter
from chatdku.core.tools.major_requirements import MajorRequirementsLookup
from chatdku.core.tools.get_prerequisites import PrerequisiteLookup


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
        SyllabusLookupOuter(),
        MajorRequirementsLookup,
        PrerequisiteLookup,
        # NOTE: This tool is using 2026 Spring Semester's schedule
        # Should update the db before using this tool
        # CourseScheduleLookup,
    ]

    return base_tools
