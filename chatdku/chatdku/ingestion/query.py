#!/usr/bin/env python3

from llama_index.core import VectorStoreIndex, get_response_synthesizer
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever, TransformRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.postprocessor.colbert_rerank import ColbertRerank
from llama_index.core.llms import LLM
from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.query_pipeline import QueryPipeline, CustomQueryComponent
from llama_index.core.prompts.base import PromptTemplate
from llama_index.core.prompts.prompt_type import PromptType
from llama_index.core.bridge.pydantic import Field
from typing import Dict, Any
import asyncio

from chatdku.config import config
from chatdku.setup import setup, use_phoenix

DEFAULT_CONDENSE_PROMPT = (
    "I have a conversation between a human user and an AI assistant, containing "
    "a previous conversation between the user and the assistant, and a current "
    "user message that continues the previous conversation. I want to get a summary "
    "of the previous conversation and an explanation so that when these are sent"
    "to another AI assistant, the conversation could be continued.\n\n"
    "Respond with the following three parts:\n"
    "1. Repeat the user message verbatim. "
    'Begin this part with "Current user message:"\n'
    "2. Summary of the previous conversation, emphasizing the parts that are "
    'related to the current message. Begin this part with "Summary of our previous conversation:". '
    "If there is no previous conversation, skip this part entirely.\n"
    "3. Explain the current user message regarding how it connects with the summary you gave. "
    'Begin this part with "Explanation:"\n\n'
    "Previous conversation:\n"
    "##########\n"
    "{previous}\n"
    "##########\n\n"
    "Current user message:\n"
    "##########\n"
    "{current}\n"
    "##########"
)


class CondenseChatHistory(CustomQueryComponent):
    """
    Condense the previous conversations and connect with the current user message

    FIXME: The previous conversations might exceed the context window, which is not yet handled.
    """

    llm: LLM = Field()
    condense_prompt: str = Field(default=DEFAULT_CONDENSE_PROMPT)

    def _validate_component_inputs(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component inputs during run_component."""
        return input

    @property
    def _input_keys(self) -> set:
        return {"chat_history"}

    @property
    def _output_keys(self) -> set:
        return {"query_str"}

    async def _arun_component(self, **kwargs: Any) -> Dict[str, Any]:
        chat_history = kwargs["chat_history"].copy()
        if len(chat_history) > 1:
            previous = "\n\n".join([str(c) for c in chat_history[:-1]])
        else:
            previous = ""
        rewrite_str = self.condense_prompt.format(
            previous=previous, current=str(chat_history[-1])
        )
        response = await self.llm.acomplete(rewrite_str)
        return {"query_str": response.text}

    def _run_component(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.arun_component(**kwargs))


def get_pipeline(
    retriever_type: str = "fusion",
    hyde: bool = True,
    vector_top_k: int = 10,
    bm25_top_k: int = 10,
    fusion_top_k: int = 10,
    fusion_mode: FUSION_MODES = FUSION_MODES.RECIPROCAL_RANK,
    num_queries: int = 3,
    synthesize_response: bool = True,
    response_mode: ResponseMode = ResponseMode.COMPACT,
    weight1: float = 0.6,
    weight2: float = 0.4,
    colbert_rerank: bool = True,
    rerank_top_n=10,
) -> QueryPipeline:
    """
    Constructs a RAG query pipeline.

    Args:
        retriever_type: Type of retriever to use.
            Supported values are `vector` and `fusion`.
        hyde: If `True`, first use HyDE (Hypothetical Document Embeddings)
            to transform the query string before retrieval.
        vector_top_k: Top k similar nodes to retrieve using vector retriever
            (they are the inputs to fusion retriever if used).
        bm25_top_k: Top k similar nodes to retrieve using BM25 retriever
            (they are the inputs to fusion retriever if used).
        fusion_top_k: Top k similar documents to retrieve using fusion retriever.
        fusion_mode: How fusion retriever should calculate the score of the nodes.
            See `llama_index.core.retrievers.fusion_retriever.FUSION_MODES` for details.
        num_queries: Number of queries to generate for fusion retriever.
        synthesize_response: Synthesize responses using LLM if `True`,
            or output a list of nodes retrived if `False`.
        response_mode: Mode of response synthesis, see
            `llama_index.core.response_synthesizers.ResponseMode` for details.
        weight1, weight2: Weights for the distribution based fusion.
        cohere_rerank: boolean value to decide to use cohere reranking
        cohere_top_k: Top k relevant nodes to retrieve with Cohere Rerank

    Returns:
        A query pipeline that could be executed by supplying input to its `run()` method.

    Raises:
        ValueError: If an unsupported or invalid parameters are provided.
    """

    db = chromadb.PersistentClient(path=config.chroma_db)
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

    if hyde:
        # NOTE: `HyDEQueryTransform` would effectively not work if used as an
        # component of the query pipeline by itself, since it returns a `QueryBundle`
        # with custom embedding strings that would be dropped when passed down the
        # pipeline as only the `query_str` attribute would be sent to the next
        # component.
        vector_retriever = TransformRetriever(
            retriever=vector_retriever,
            query_transform=HyDEQueryTransform(include_original=True),
        )

    if retriever_type == "vector":
        retriever = vector_retriever

    elif retriever_type == "fusion":
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=bm25_top_k
        )

        # NOTE: I am not sure why, but when using this retriever you MUST supply an LLM,
        # otherwise errors will be reported at the synthesizer stage. While this might
        # be due to the need of using an LLM at the query generation stage, it still
        # won't work if you set num_queries=1.
        # NOTE: by Cody Jul 3, in the documentation I found that "num_queries=1" is to disable query generation
        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            similarity_top_k=fusion_top_k,
            mode=fusion_mode,
            # num_queries=num_queries,
            use_async=True,
            verbose=True,
        )

    elif retriever_type == "distribution based fusion":
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=bm25_top_k
        )

        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            retriever_weights=[weight1, weight2],
            similarity_top_k=fusion_top_k,
            mode="dist_based_score",
            num_queries=num_queries,
            use_async=True,
            verbose=True,
        )

    else:
        raise ValueError(f"Unsupported retriever_type: {retriever_type}")

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": CondenseChatHistory(llm=Settings.llm),
            "retriever": retriever,
        }
    )
    pipeline.add_link("input", "retriever")

    if colbert_rerank:
        colbert_reranker = ColbertRerank(
            top_n=rerank_top_n,
            model="colbert-ir/colbertv2.0",
            tokenizer="colbert-ir/colbertv2.0",
            keep_retrieval_score=True,
        )

        pipeline.add_modules(
            {
                "rerank": colbert_reranker,
            }
        )
        pipeline.add_link("input", "rerank", dest_key="query_str")
        pipeline.add_link("retriever", "rerank", dest_key="nodes")

    if synthesize_response:
        requirements = (
            "State the sources of all contexts referenced, include links in Markdown if availble. "
            "Be organized and use bullet points if needed. "
            "The contexts might contain unrelated information or non-DKU resources. "
            "Always prefer DKU resources first. "
            "You may include other resources (including even Duke resources) only as "
            "a second option unless directly asked, or that resource is clearly "
            "available to the DKU community via means such as a partnership with DKU. "
            "For you to appear more human to the user, all the context given should be "
            "treated as your internal knowledge. "
            'Thus, never use phrases like "based on the provided context". '
            "Your internal operation should also not be transparent to the user, "
            'so you should not mention phrases like "I\'ve refined my answer".'
        )

        qa_prompt = (
            "Context information is below.\n"
            "##########\n"
            "{context_str}\n"
            "##########\n\n"
            "Given the context information and not prior knowledge, "
            "answer the query. " + requirements + "\n\n"
            "Query:\n"
            "##########\n"
            "{query_str}\n"
            "##########\n\n"
        )
        qa_prompt = PromptTemplate(qa_prompt, prompt_type=PromptType.QUESTION_ANSWER)

        refine_prompt = (
            "The original query is as follows:\n"
            "##########\n"
            "{query_str}\n"
            "##########\n\n"
            "We have provided an existing answer:\n"
            "##########\n"
            "{existing_answer}\n"
            "##########\n\n"
            "We have the opportunity to refine the existing answer "
            "(only if needed) with some more context below.\n"
            "##########\n"
            "{context_msg}\n"
            "##########\n\n"
            "Given the new context, refine the original answer to better "
            "answer the query. "
            "If the context isn't useful, return the original answer. " + requirements
        )
        refine_prompt = PromptTemplate(refine_prompt, prompt_type=PromptType.REFINE)

        pipeline.add_modules(
            {
                "synthesizer": get_response_synthesizer(
                    text_qa_template=qa_prompt,
                    refine_template=refine_prompt,
                    response_mode=response_mode,
                    streaming=True,
                )
            }
        )
        pipeline.add_link("input", "synthesizer", dest_key="query_str")
        if colbert_rerank:
            pipeline.add_link("rerank", "synthesizer", dest_key="nodes")
        else:
            pipeline.add_link("retriever", "synthesizer", dest_key="nodes")

    return pipeline


def main():
    setup(add_system_prompt=True)
    use_phoenix()
    pipeline = get_pipeline()
    chat_history = []
    while True:
        try:
            print("*" * 32)
            inp = input("Enter your query about DKU: ")
            chat_history.append(ChatMessage(role=MessageRole.USER, content=inp))
            stream = pipeline.run(chat_history=chat_history)
            print("+" * 32)
            stream.print_response_stream()
            chat_history.append(
                ChatMessage(
                    role=MessageRole.ASSISTANT, content=str(stream.get_response())
                )
            )
        except EOFError:
            break


if __name__ == "__main__":
    main()
