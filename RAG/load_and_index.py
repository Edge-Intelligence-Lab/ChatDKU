#!/usr/bin/env python3

import os
import nltk
import chromadb
import pickle
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    VectorStoreIndex,
)
from llama_index.readers.file import UnstructuredReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
from settings import parse_args_and_setup

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition


def load_and_index(
    data_dir: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict = {},
    # NOTE: Multiprocessing appears to have issues with HuggingFaceEmbedding,
    # please use only a single process for now.
    pipeline_workers: int = 1,
):
    # Required for UnstructuredReader
    nltk.download("averaged_perceptron_tagger")
    reader = UnstructuredReader()

    documents_path = os.path.join(data_dir, "documents.pkl")
    if os.path.exists(documents_path):
        with open(documents_path, "rb") as f:
            documents = pickle.load(f)
    else:
        reader = UnstructuredReader()
        documents = SimpleDirectoryReader(
            data_dir,
            recursive=True,
            required_exts=[".html", ".htm", ".pdf", ".csv"],
            file_extractor={
                ".htm": reader,
                ".html": reader,
                ".pdf": reader,
                ".csv": reader,
            },
        ).load_data()
        with open(documents_path, "wb") as f:
            pickle.dump(documents, f)

    print("Length of documents:",len(documents))

    trans = []
    if text_spliter == "sentence_splitter":
        from llama_index.core.node_parser import SentenceSplitter

        trans.append(SentenceSplitter(**text_spliter_args))
    else:
        raise ValueError(f"Unsupported text_splitter: {text_spliter}")
    trans.append(Settings.embed_model)

    db = chromadb.PersistentClient(path="./chroma_db", settings=chromadb.Settings(allow_reset=True))
    db.reset()  # Clear previously stored data in vector database
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    docstore = SimpleDocumentStore()

    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
        docstore=docstore,
    )
    pipeline_cache = "./pipeline_storage"
    if os.path.exists(pipeline_cache):
        pipeline.load(pipeline_cache)
    pipeline.run(documents=documents, num_workers=pipeline_workers)
    pipeline.persist(pipeline_cache)

    VectorStoreIndex.from_vector_store(vector_store)
    docstore.persist("./docstore")


def main():
    parse_args_and_setup()
    load_and_index(
        data_dir="../RAG_data",
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        pipeline_workers=1,
    )


if __name__ == "__main__":
    main()

