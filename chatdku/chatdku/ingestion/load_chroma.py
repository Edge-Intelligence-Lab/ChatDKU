#!/usr/bin/env python3

import os
import pickle
import chromadb
import argparse
from llama_index.core import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.ingestion import IngestionPipeline
from typing import Any
from chatdku.setup import setup
from chatdku.config import config

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype


# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype
unstructured.partition.auto.partition = partition


def load_chroma(
    pipeline_cache_path: str,
    collection: str = None,
    documents=None,
    reset: bool = False,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict[str, Any] = {},
    extractors: list[str] = [],
    use_recursive_directory_summarize: bool = False,
    # NOTE: Multiprocessing appears to have issues with HuggingFaceEmbedding and LlamaCPP,
    # please use only a single process for now.
    pipeline_workers: int = 1,
):
    """
    Populate the ChromaDB. If you run this from the terminal it will re-populate
    the ChromaDB from the start. If you import the function load_chroma(), you can add documents
    without resetting Redis.

    documents: It will accept Llamaindex documents (files ending with .pkl).
        If you leave it out, it will take documents from config.documents_path.
        You can fill this in to add documents to redis.
    collection: You can set this to any other name to create another collection in chromaDB but
        for Redis.
    reset: Whether to overwrite the data already on the DB.
    """
    if documents is None:
        with open(config.documents_path, "rb") as f:
            documents = pickle.load(f)
    if collection is None:
        collection = config.chroma_collection

    trans = []

    supported_extractors = ["title", "keyword", "questions_answered", "summary"]
    for e in extractors:
        if e not in supported_extractors:
            raise ValueError(f"Unsupported extractor: {e}")

    if "title" in extractors:
        from llama_index.core.extractors import TitleExtractor

        trans.append(TitleExtractor())

    if text_spliter == "sentence_splitter":
        from llama_index.core.node_parser import SentenceSplitter

        trans.append(SentenceSplitter(**text_spliter_args))
    else:
        raise ValueError(f"Unsupported text_splitter: {text_spliter}")

    if use_recursive_directory_summarize:
        from recursive_directory_summarize import RecursiveDirectorySummarize

        trans.append(RecursiveDirectorySummarize())

    if "keyword" in extractors:
        from llama_index.core.extractors import KeywordExtractor

        trans.append(KeywordExtractor())

    if "questions_answered" in extractors:
        from llama_index.core.extractors import QuestionsAnsweredExtractor

        trans.append(QuestionsAnsweredExtractor())

    if "summary" in extractors:
        from llama_index.core.extractors import SummaryExtractor

        trans.append(SummaryExtractor())

    trans.append(Settings.embed_model)

    db = chromadb.PersistentClient(
        path=config.chroma_db, settings=chromadb.Settings(allow_reset=True)
    )

    if reset:
        db.reset()  # Clear previously stored data in vector database
    chroma_collection = db.get_or_create_collection(collection)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # NOTE: Currently, LlamaIndex has bug with using both caching and docstore.
    # I am using only caching here and there is not much need for attaching a
    # docstore for deduplication anyways.
    # See https://github.com/run-llama/llama_index/issues/14068 for details.
    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
    )
    if os.path.exists(pipeline_cache_path):
        pipeline.load(pipeline_cache_path)

    pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)

    nodes = pipeline.run(
        documents=documents, num_workers=pipeline_workers, show_progress=True
    )
    pipeline.persist(pipeline_cache_path)
    print("nodes over")
    #
    # docstore = SimpleDocumentStore()
    # docstore.add_documents(nodes)
    # docstore.persist(config.docstore_path)
    # print("docstore over")


def main(documents_path=None, collection_name=None):
    setup(use_llm=False)

    if documents_path is None:
        documents = None
    else:
        with open(documents_path, "r") as f:
            documents = pickle.load(f)

    load_chroma(
        reset=True,
        documents=documents,
        collection=collection_name,
        pipeline_cache_path=str(config.pipeline_cache),
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        extractors=[],
        use_recursive_directory_summarize=False,
        pipeline_workers=1,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load the specified .pkl file into chroma."
    )
    parser.add_argument(
        "--documents_path",
        type=str,
        default=config.documents_path,
        help="The directory containing the data",
    )
    parser.add_argument(
        "--collection_name",
        type=str,
        default=config.chroma_collection,
        help="Name of the chroma collection.",
    )
    args = parser.parse_args()

    main(args.documents_path, args.collection_name)
