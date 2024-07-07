#!/usr/bin/env python3

import os
from argparse import ArgumentParser
from pathlib import Path
import pickle
import chromadb
from llama_index.core import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
from typing import Any
from settings import setup
from update_data import update_data, hash_directory

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition

from config import Config
config = Config()


def load_and_index(
    update: bool,
    read_only: bool,
    data_dir: str,
    pipeline_cache_path: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict[str, Any] = {},
    extractors: list[str] = [],
    use_recursive_directory_summarize: bool = False,
    # NOTE: Multiprocessing appears to have issues with HuggingFaceEmbedding and LlamaCPP,
    # please use only a single process for now.
    pipeline_workers: int = 1,
):
    documents_path = os.path.join(config.data_dir, config.documents_path)
    hash_path = os.path.join("./", "hash.pkl")
    now_hash = hash_directory(data_dir)

    if update:
        print(f"Force updating {documents_path}")
        documents = update_data(data_dir)
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
                documents = update_data(data_dir)
                now_hash = hash_directory(data_dir)
                with open(hash_path, "wb") as hf:
                    pickle.dump(now_hash, hf)
                print(f"Hashes of data files written at {hash_path}")

    else:
        print(
            f"Either {documents_path} or {hash_path} does not exist, updating {documents_path}"
        )
        documents = update_data(data_dir)
        now_hash = hash_directory(data_dir)
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash, hf)
        print(f"Hashes of data files written at {hash_path}")

    print("Data reading done")
    if read_only:
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
        path=config.chunk_overlap, settings=chromadb.Settings(allow_reset=True)
    )
    db.reset()  # Clear previously stored data in vector database
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
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
    nodes = pipeline.run(
        documents=documents, num_workers=pipeline_workers, show_progress=True
    )
    pipeline.persist(pipeline_cache_path)

    docstore = SimpleDocumentStore()
    docstore.add_documents(nodes)
    docstore.persist(config.docstore_path)


def main():
    parser = ArgumentParser()
    parser.add_argument("-u", "--update", action="store_true")
    parser.add_argument("-r", "--read-only", action="store_true")
    parser.add_argument("-d", "--data_dir", type=Path, default=Path("/opt/RAG_data"))
    parser.add_argument(
        "-c",
        "--pipeline-cache",
        type=Path,
        default=Path("./pipeline_storage"),
    )
    args = parser.parse_args()
    setup()

    load_and_index(
        update=args.update,
        read_only=args.read_only,
        data_dir=str(args.data_dir),
        pipeline_cache_path=str(args.pipeline_cache),
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        extractors=[],
        use_recursive_directory_summarize=False,
        pipeline_workers=1,
    )


if __name__ == "__main__":
    main()
