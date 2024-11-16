#!/usr/bin/env python3

import os
import pickle
import chromadb
from typing import Any
import argparse
import json
import hashlib

from redis import Redis
from redisvl.schema import IndexSchema
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.readers.file import UnstructuredReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_parse import LlamaParse
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.extractors import (
    TitleExtractor,
    KeywordExtractor,
    QuestionsAnsweredExtractor,
    SummaryExtractor,
)
from llama_index.vector_stores.redis import RedisVectorStore

from setup import setup
from config import config

import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype


import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition
def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def record_directory_state(directory):
    state = {}
    for root, _, files in os.walk(directory):
        for name in files:
            file_path = os.path.join(root, name)
            relative_path = os.path.relpath(file_path, directory)
            state[relative_path] = calculate_sha256(file_path)
    return state


def compare_directory_state(old_state, new_state):
    added = []
    removed = []
    modified = []

    old_files = set(old_state.keys())
    new_files = set(new_state.keys())

    added_files = new_files - old_files
    removed_files = old_files - new_files

    for file in added_files:
        added.append(file)

    for file in removed_files:
        removed.append(file)

    for file in old_files & new_files:
        if old_state[file] != new_state[file]:
            modified.append(file)

    return added, removed, modified


def export_changes(added, removed, modified, output_file):
    changes = {"added": added, "removed": removed, "modified": modified}
    if os.path.exists(output_file):
        with open(output_file, "w") as f:
            json.dump(changes, f, indent=4)


def change_detect(data_dir):

    output_file = data_dir+"/changed_data.json"
    state_file = data_dir+"/data_state.json"

    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            old_state = json.load(f)
    else:
        old_state = {}
        with open(state_file, "w") as f:
            json.dump(old_state, f)
        
    if not os.path.exists(output_file):
        with open(output_file, "w") as f:
            json.dump({}, f)

    new_state = record_directory_state(data_dir)

    added, removed, modified = compare_directory_state(old_state, new_state)

    export_changes(added, removed, modified, output_file)

    # Load changed data
    with open(output_file, "r") as f:
        changed_data = json.load(f)

    new_files = changed_data["added"] + changed_data["modified"]
    new_files = list(data_dir + "/" + new_file for new_file in new_files)
    timed_files = changed_data["modified"] + changed_data["removed"]
    timed_files = list(data_dir + "/" + timed_file for timed_file in timed_files)

    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=4)

    # Update documents
    #documents_path = os.path.join(data_dir, "new_parser_documents.pkl")
    ddocuments_path = os.path.join(config.data_dir, config.documents_path)
    if not os.path.exists(documents_path):
        with open(documents_path, "wb") as f:
            pickle.dump([], f)

    with open(documents_path, "rb") as file:
        documents = pickle.load(file)
    print(f"Loaded documents from {documents_path}")

    for document in documents:
        if document.metadata["file_path"] in timed_files:
            documents.remove(document)



    if len(new_files + timed_files) == 0:
        print("Nothing has changed")
        return

    print(
        "Added",
        len(changed_data["added"]),
        "documents\n",
        "Modified",
        len(changed_data["modified"]),
        "documents\n",
        "Removed",
        len(changed_data["removed"]),
        "documents\n",
    )

    reader = UnstructuredReader()
    llama_parse_api_key = "llx-dwGAqjLq7SqCXu7u9y2lBDyyIlnVvbh0pSJUed1toAsnwseQ"
    pdf_parser = LlamaParse(
        api_key=llama_parse_api_key,
        result_type="markdown",
        verbose=True,
    )
    new_documents = SimpleDirectoryReader(
        input_files=new_files,
        recursive=True,
        required_exts=[".html", ".htm", ".pdf", ".csv"],
        file_extractor={
            ".htm": reader,
            ".html": reader,
            ".pdf": pdf_parser,
            ".csv": reader,
        },
    ).load_data()

    documents = documents + new_documents
    


    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)

    print("Document successfully update")

def set_state(data_dir):
    state_file = "data_state.json"
    new_state = record_directory_state(data_dir)
    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=4)

def change_update(data_dir):

    output_file = "changed_data.json"

    # Load changed data
    with open(output_file, "r") as f:
        changed_data = json.load(f)

    new_files = changed_data["added"] + changed_data["modified"]
    new_files = list(data_dir + "/" + new_file for new_file in new_files)
    timed_files = changed_data["modified"] + changed_data["removed"]
    timed_files = list(data_dir + "/" + timed_file for timed_file in timed_files)

    # If no data_update
    if len(new_files + timed_files) == 0:
        print("Nothing has changed")
        return

    print(
        "Added",
        len(changed_data["added"]),
        "documents\n",
        "Modified",
        len(changed_data["modified"]),
        "documents\n",
        "Removed",
        len(changed_data["removed"]),
        "documents\n",
    )


def load_and_index(
    data_dir: str,
    pipeline_cache_path: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict[str, Any] = {},
    extractors: list[str] = [],
    use_recursive_directory_summarize: bool = False,
    pipeline_workers: int = 1,
):
    documents_path = os.path.join(config.data_dir, config.documents_path)

    with open(documents_path, 'rb') as f:
        documents = pickle.load(f)
    
    trans = []
    
    supported_extractors = ["title", "keyword", "questions_answered", "summary"]
    for e in extractors:
        if e not in supported_extractors:
            raise ValueError(f"Unsupported extractor: {e}")
    
    if "title" in extractors:
        trans.append(TitleExtractor())
    
    if text_spliter == "sentence_splitter":
        trans.append(SentenceSplitter(**text_spliter_args))
    else:
        raise ValueError(f"Unsupported text_spliter: {text_spliter}")
    
    if use_recursive_directory_summarize:
        from recursive_directory_summarize import RecursiveDirectorySummarize
        trans.append(RecursiveDirectorySummarize())
    
    if "keyword" in extractors:
        trans.append(KeywordExtractor())
    
    if "questions_answered" in extractors:
        trans.append(QuestionsAnsweredExtractor())
    
    if "summary" in extractors:
        trans.append(SummaryExtractor())
    
    db = chromadb.PersistentClient(
        path=config.chroma_db, settings=chromadb.Settings(allow_reset=True)
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
    print("nodes over")

    
    trans.append(Settings.embed_model)
    
    # 设置Redis向量存储
    redis_client = Redis.from_url("redis://localhost:6379")
    
    custom_schema = IndexSchema.from_dict(
        {
            "index": {
                "name": "idx:test",
                "prefix": "test_doc",
                "key_separator": ":",
            },
            "fields": [
                {"type": "tag", "name": "id"},
                {"type": "tag", "name": "doc_id"},
                {"type": "text", "name": "text"},
                {"type": "tag", "name": "groups"},
                {"type": "tag", "name": "file_path"},
                {"type": "tag", "name": "file_name"},
                {"type": "tag", "name": "last_modified_date"},
                {
                    "type": "vector",
                    "name": "vector",
                    "attrs": {
                        "dims": 1024,
                        "algorithm": "hnsw",
                        "distance_metric": "cosine",
                    },
                },
            ],
        }
    )

    custom_schema.to_yaml("custom_schema.yaml")
    
    vector_store = RedisVectorStore(
        redis_client=redis_client, schema=custom_schema, overwrite=True
    )

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
    
    
def main(data_dir):
    setup(add_system_prompt=True)
    change_detect(data_dir)
    #Uncomment before running
    '''
    load_and_index(
        data_dir=str(data_dir),
        pipeline_cache_path=str(config.pipeline_cache),
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        extractors=[],
        use_recursive_directory_summarize=False,
        pipeline_workers=1,
    )
    '''
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=str)
    args = parser.parse_args()
    main(args.data_dir)
