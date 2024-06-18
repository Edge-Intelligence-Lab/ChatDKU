#!/usr/bin/env python3

from llama_index.core import VectorStoreIndex, get_response_synthesizer
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever, TransformRetriever
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.query_pipeline import QueryPipeline, InputComponent
import phoenix as px
from llama_index.core.callbacks.global_handlers import set_global_handler
from settings import parse_args_and_setup


def get_pipeline(
    retriever_type: str = "fusion",
    hyde: bool = True,
    vector_top_k: int = 5,
    bm25_top_k: int = 5,
    fusion_top_k: int = 5,
    num_queries: int = 3,
    synthesize_response: bool = True,
    response_mode: ResponseMode = ResponseMode.COMPACT,
) -> QueryPipeline:
    """
    Constructs a RAG query pipeline.

    Args:
        retriever_type: Type of retriever to use. Supported values are `vector` and `fusion`.
        hyde: If `True`, first use HyDE (Hypothetical Document Embeddings) to transform the query string before retrieval.
        vector_top_k: Top k similar nodes to retrieve using vector retriever (they are the inputs to fusion retriever if used).
        bm25_top_k: Top k similar nodes to retrieve using BM25 retriever (they are the inputs to fusion retriever if used).
        fusion_top_k: Top k similar documents to retrieve using fusion retriever.
        num_queries: Number of queries to generate for fusion retriever.
        synthesize_response: Synthesize responses using LLM if `True`, or output a list of nodes retrived if `False`.
        response_mode: Mode of response synthesis, see `llama_index.core.response_synthesizers.ResponseMode` for more details.

    Returns:
        A query pipeline that could be executed by supplying input to its `run()` method.

    Raises:
        ValueError: If an unsupported or invalid parameters are provided.
    """

    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

    if retriever_type == "vector":
        retriever = vector_retriever

    elif retriever_type == "fusion":
        docstore = SimpleDocumentStore.from_persist_path("./docstore")
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=bm25_top_k
        )

        # NOTE: I am not sure why, but when using this retriever you MUST supply an LLM,
        # otherwise errors will be reported at the synthesizer stage. While this might
        # be due to the need of using an LLM at the query generation stage, it still
        # won't work if you set num_queries=1.
        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            similarity_top_k=fusion_top_k,
            num_queries=num_queries,
            use_async=True,
            verbose=True,
        )

    else:
        raise ValueError(f"Unsupported retriever_type: {retriever_type}")

    if hyde:
        # NOTE: `HyDEQueryTransform` would effectively not work if used as an
        # component of the query pipeline by itself, since it returns a `QueryBundle`
        # with custom embedding strings that would be dropped when passed down the
        # pipeline as only the `query_str` attribute would be sent to the next
        # component.
        retriever = TransformRetriever(
            retriever=retriever,
            query_transform=HyDEQueryTransform(include_original=True),
        )

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": InputComponent(),
            "retriever": retriever,
        }
    )
    pipeline.add_link("input", "retriever")

    if synthesize_response:
        pipeline.add_modules(
            {
                "synthesizer": get_response_synthesizer(
                    response_mode=response_mode, streaming=True
                )
            }
        )
        pipeline.add_link("input", "synthesizer", dest_key="query_str")
        pipeline.add_link("retriever", "synthesizer", dest_key="nodes")

    return pipeline


def main():
    parse_args_and_setup()

    px.launch_app()
    set_global_handler("arize_phoenix")

    pipeline = get_pipeline(
        retriever_type="fusion",
        hyde=True,
        vector_top_k=5,
        bm25_top_k=5,
        fusion_top_k=5,
        num_queries=3,
        synthesize_response=True,
        response_mode=ResponseMode.COMPACT,
    )

    while True:
        try:
            print("*" * 32)
            query = input("> ")
            output = pipeline.run(input=query)
            print("+" * 32)
            print(output)
        except EOFError:
            break


if __name__ == "__main__":
    main()
