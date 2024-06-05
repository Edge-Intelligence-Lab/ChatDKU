#!/usr/bin/env python3

import chromadb
from llama_index.core import VectorStoreIndex, get_response_synthesizer
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.query_pipeline import QueryPipeline, InputComponent
from pprint import pp
from settings import parse_args_and_setup


def get_pipeline(
    vector_top_k: int = 5,
    bm25_top_k: int = 5,
    fusion_top_k: int = 5,
    num_queries: int = 3,
    response_mode: ResponseMode = ResponseMode.COMPACT,
):
    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

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

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": InputComponent(),
            "retriever": retriever,
            "synthesizer": get_response_synthesizer(response_mode=response_mode),
        }
    )
    pipeline.add_link("input", "retriever")
    pipeline.add_link("input", "synthesizer", dest_key="query_str")
    pipeline.add_link("retriever", "synthesizer", dest_key="nodes")

    return pipeline


def main():
    parse_args_and_setup()
    pipeline = get_pipeline(
        vector_top_k=5,
        bm25_top_k=5,
        fusion_top_k=5,
        num_queries=3,
        response_mode=ResponseMode.COMPACT,
    )

    while True:
        try:
            print("*" * 32)
            query = input("> ")
            output, intermediates = pipeline.run_with_intermediates(input=query)
            print("+" * 32)
            for k, v in intermediates.items():
                print(f"{k}:")
                pp(v.outputs)
                print("+" * 32)
            print(output)
        except EOFError:
            break


if __name__ == "__main__":
    main()
