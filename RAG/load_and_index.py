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
from settings import parse_args_and_setup
from update_data import update_data

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition

import hashlib

def hash_file(filename):
    h = hashlib.sha256()
    with open(filename, 'rb') as file:
        while True:
            chunk = file.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def hash_directory(directory):
    all_hashes = ''
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            file_hash = hash_file(filepath)
            all_hashes += file_hash
    final_hash = hashlib.sha256(all_hashes.encode('utf-8')).hexdigest()
    return final_hash


def load_and_index(
    data_dir: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict = {},
    # NOTE: Multiprocessing appears to have issues with HuggingFaceEmbedding,
    # please use only a single process for now.
    pipeline_workers: int = 1,
):

    documents_path = os.path.join(data_dir, "documents.pkl")
    hash_path= os.path.join("./","hash.pkl")
    now_hash=hash_directory(data_dir)
    if os.path.exists(documents_path) and os.path.exists(hash_path):
        with open(hash_path, "rb") as f:
            origin_hash=pickle.load(f)
            if(origin_hash==now_hash):
                with open(documents_path, "rb") as file:
                    documents = pickle.load(file)
            else:
                documents=update_data()
                with open(hash_path, "wb") as hf:
                    pickle.dump(now_hash,hf)
        
    else:
        documents=update_data()
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash,hf)

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

    #The current llamindex pipeline_cache has bug and cannot be updated on its own. 
    #Please remove pipeline_cache from your personal directory and do not add any related functions for the time being.
    
    pipeline.run(documents=documents, num_workers=pipeline_workers)

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


