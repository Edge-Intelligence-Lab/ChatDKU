#!/usr/bin/env python3

import os
import pickle
import chromadb
from llama_index.core import (
    Settings,
    VectorStoreIndex,
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
from typing import Any
from settings import parse_args_and_setup, Setting
from update_data import update_data, hash_directory

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
    text_spliter_args: dict[str, Any] = {},
    extractors: list[str] = [],
    use_recursive_directory_summarize: bool = False,
    # NOTE: Multiprocessing appears to have issues with HuggingFaceEmbedding and LlamaCPP,
    # please use only a single process for now.
    pipeline_workers: int = 1,
):
    documents_path = os.path.join(data_dir, "documents.pkl")
    hash_path = os.path.join("./", "hash.pkl")
    now_hash = hash_directory(data_dir)

    if Setting.update:
        print(f"Force updating {documents_path}")
        documents = update_data()
        now_hash = hash_directory(data_dir)
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash, hf)
        print(f"Hashes of data files written at {hash_path}")

    elif os.path.exists(documents_path) and os.path.exists(hash_path):
        print(f"Both {documents_path} and {hash_path} exist")
        with open(hash_path, "rb") as f:
            origin_hash = pickle.load(f)
            print(f"Loaded hashes from {origin_hash}")
            if origin_hash == now_hash:
                print(f"Hashes match, loading documents from {documents_path}")
                with open(documents_path, "rb") as file:
                    documents = pickle.load(file)
                print(f"Loaded documents from from {documents_path}")
            else:
                print(f"Hashes disagree with data files, updating {documents_path}")
                documents = update_data()
                now_hash = hash_directory(data_dir)
                with open(hash_path, "wb") as hf:
                    pickle.dump(now_hash, hf)
                print(f"Hashes of data files written at {hash_path}")

    else:
        print(
            f"Either {documents_path} or {hash_path} does not exist, updating {documents_path}"
        )
        documents = update_data()
        now_hash = hash_directory(data_dir)
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash, hf)
        print(f"Hashes of data files written at {hash_path}")

    print("Data reading done")
    if Setting.read_only:
        return

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
        path="./chroma_db", settings=chromadb.Settings(allow_reset=True)
    )
    db.reset()  # Clear previously stored data in vector database
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    docstore = SimpleDocumentStore()

    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
        docstore=docstore,
    )

    # The current llamindex pipeline_cache has bug and cannot be updated on its own.
    # Please remove pipeline_cache from your personal directory and do not add any related functions for the time being.

    pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)
    VectorStoreIndex.from_vector_store(vector_store)
    docstore.persist("./docstore")


def main():
    parse_args_and_setup()
    load_and_index(
        data_dir=Setting.data_dir,
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        extractors=[],
        use_recursive_directory_summarize=False,
        pipeline_workers=1,
    )


if __name__ == "__main__":
    main()
