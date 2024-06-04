#!/usr/bin/env python3

import chromadb
from llama_index.core import VectorStoreIndex, get_response_synthesizer
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.query_pipeline import QueryPipeline, InputComponent
from llama_index.core.response_synthesizers import ResponseMode
from pprint import pp
from settings import parse_args_and_setup


def query(response_mode=ResponseMode.COMPACT):
    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    index = VectorStoreIndex.from_vector_store(vector_store)

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": InputComponent(),
            "retriever": index.as_retriever(),
            "synthesizer": get_response_synthesizer(response_mode=response_mode),
        }
    )
    pipeline.add_link("input", "retriever")
    pipeline.add_link("input", "synthesizer", dest_key="query_str")
    pipeline.add_link("retriever", "synthesizer", dest_key="nodes")

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


def main():
    parse_args_and_setup()
    query(response_mode=ResponseMode.COMPACT)


if __name__ == "__main__":
    main()
