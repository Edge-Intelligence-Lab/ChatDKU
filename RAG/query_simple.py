#!/usr/bin/env python3

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext


if __name__ == "__main__":
    import settings  # noqa # pyright: ignore

    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )

    # TODO: Query engine could be composed from, for example, the retrieval and
    # response synthesis components or even customized. Additionally, a query
    # pipeline could also be established where the LLM would play a role in
    # retrieval, reranking, and response synthesis stages.
    query_engine = index.as_query_engine()

    while True:
        try:
            prompt = input("> ")
            response = query_engine.query(prompt)
            print(response)
        except EOFError:
            break
