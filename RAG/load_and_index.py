#!/usr/bin/env python3

import os
import chromadb
import pickle
from llama_index.core import (
    Settings,
    VectorStoreIndex,
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
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

# FIXME: Fix `HuggingFaceEmbedding` not working in `IngestionPipeline` Multiprocessing.
# This is just a monkey patch and we should look for its root cause if possible.
# See: https://github.com/run-llama/llama_index/issues/13956
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.ingestion.pipeline import get_transformation_hash
from llama_index.core.ingestion.cache import IngestionCache
from llama_index.core.schema import BaseNode, TransformComponent
from typing import Any, List, Optional, Sequence
import llama_index.core.ingestion.pipeline


def run_transformations_patched(
    nodes: List[BaseNode],
    transformations: Sequence[TransformComponent],
    in_place: bool = True,
    cache: Optional[IngestionCache] = None,
    cache_collection: Optional[str] = None,
    **kwargs: Any,
) -> List[BaseNode]:
    """Run a series of transformations on a set of nodes.

    Args:
        nodes: The nodes to transform.
        transformations: The transformations to apply to the nodes.

    Returns:
        The transformed nodes.
    """
    if not in_place:
        nodes = list(nodes)

    for transform in transformations:
        # Reinitialize `HuggingFaceEmbedding` if necessary
        if isinstance(transform, HuggingFaceEmbedding):
            transform = HuggingFaceEmbedding(
                model_name=transform.model_name,
                # NOTE: only needed in my case, you only need to pass in the parameters needed for your project
                trust_remote_code=True,
            )

        if cache is not None:
            hash = get_transformation_hash(nodes, transform)
            cached_nodes = cache.get(hash, collection=cache_collection)
            if cached_nodes is not None:
                nodes = cached_nodes
            else:
                nodes = transform(nodes, **kwargs)
                cache.put(hash, nodes, collection=cache_collection)
        else:
            nodes = transform(nodes, **kwargs)

    return nodes


llama_index.core.ingestion.pipeline.run_transformations = run_transformations_patched


def load_and_index(
    data_dir: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict = {},
    # NOTE: Multiprocessing appears to have issues with HuggingFaceEmbedding,
    # please use only a single process for now.
    pipeline_workers: int = 1,
):
    documents_path = os.path.join(data_dir, "documents.pkl")
    hash_path = os.path.join("./", "hash.pkl")
    now_hash = hash_directory(data_dir)

    if Setting.update:
        documents = update_data()
        now_hash = hash_directory(data_dir)
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash, hf)

    elif os.path.exists(documents_path) and os.path.exists(hash_path):
        with open(hash_path, "rb") as f:
            origin_hash = pickle.load(f)
            if origin_hash == now_hash:
                with open(documents_path, "rb") as file:
                    documents = pickle.load(file)
            else:
                documents = update_data()
                now_hash = hash_directory(data_dir)
                with open(hash_path, "wb") as hf:
                    pickle.dump(now_hash, hf)

    else:
        documents = update_data()
        now_hash = hash_directory(data_dir)
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash, hf)

    trans = []
    if text_spliter == "sentence_splitter":
        from llama_index.core.node_parser import SentenceSplitter

        trans.append(SentenceSplitter(**text_spliter_args))
    else:
        raise ValueError(f"Unsupported text_splitter: {text_spliter}")
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

    pipeline.run(documents=documents, num_workers=pipeline_workers)

    VectorStoreIndex.from_vector_store(vector_store)
    docstore.persist("./docstore")


def main():
    parse_args_and_setup()
    load_and_index(
        data_dir=Setting.data_dir,
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        pipeline_workers=4,
    )


if __name__ == "__main__":
    main()
