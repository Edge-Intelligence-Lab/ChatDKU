#!/usr/bin/env python3

import chromadb
import nltk
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from llama_index.readers.file import UnstructuredReader

#Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype
unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

import settings  # noqa # pyright: ignore

if __name__ == "__main__":
    # Required for UnstructuredReader
    nltk.download("averaged_perceptron_tagger")
    reader = UnstructuredReader()
    documents = SimpleDirectoryReader(
        "../RAG_data",
        recursive=True,
        required_exts=[".html", ".htm", ".pdf"],
        file_extractor={
            ".htm": reader,
            ".html": reader,
            ".pdf": reader,
        },
    ).load_data()

    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # TODO: Data loading could be customized either by supplying a list of custom
    # transformations or use transformation modules explicitly. The transformation
    # modules could be used standalone or composed in the ingestion pipeline.
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
