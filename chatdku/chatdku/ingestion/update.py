#!/usr/bin/env python3

import os
import sys
import pickle
import chromadb
from typing import Any
import argparse
import json
import hashlib

import nltk
#nltk.download('averaged_perceptron_tagger_eng')

from redis import Redis
from redisvl.schema import IndexSchema
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

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

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

    output_file = os.path.join(data_dir, "changed_data.json")
    state_file = os.path.join(data_dir, "data_state.json")

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

    # Update documents
    #documents_path = os.path.join(data_dir, "new_parser_documents.pkl")
    documents_path = config.documents_path

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
    
    # 加载已解析的文件记录
    parsed_files_record = os.path.join(data_dir, "parsed_files.pkl")
    if os.path.exists(parsed_files_record):
        with open(parsed_files_record, "rb") as f:
            parsed_files = pickle.load(f)
    else:
        parsed_files = set()

    # 定义目标文件类型
    valid_extensions = {".htm", ".html", ".pdf", ".csv"}

    # 过滤掉不符合要求的文件
    new_files = [file for file in new_files if os.path.splitext(file)[1].lower() in valid_extensions]
    # 二次过滤已解析的文件
    new_files = [file for file in new_files if file not in parsed_files]
    if(len(new_files)!=0):    
        for file in new_files:
            try:
                # Parse the file
                if os.path.splitext(file)[1].lower() in valid_extensions:
                    new_document = SimpleDirectoryReader(
                        input_files=[file],
                        recursive=True,
                        required_exts=[".html", ".htm", ".pdf", ".csv"],
                        file_extractor={
                            ".htm": reader,
                            ".html": reader,
                            ".pdf": pdf_parser,
                            ".csv": reader,
                        },
                    ).load_data()

                    # Update documents and save
                    documents.extend(new_document)
                    with open(documents_path, "wb") as f:
                        pickle.dump(documents, f)

                    # Update parsed files record and save
                    parsed_files.add(file)
                    with open(parsed_files_record, "wb") as f:
                        pickle.dump(parsed_files, f)
                else:
                    print(f"Skipping unsupported file type: {file}")
            except Exception as e:
                print(f"Error parsing {file}: {e}")
                # Optionally log the error to a file
                continue  # Proceed to the next file
    else:
        new_documents=[]

    documents = documents + new_documents


    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)
    
    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=4)
    # 删除临时文件
    os.remove(parsed_files_record)

    print("Document successfully update")
    return new_documents

def set_state(data_dir):
    state_file = "data_state.json"
    new_state = record_directory_state(data_dir)
    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=4)

def load_and_index(
    new_documents,
    pipeline_cache_path: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict[str, Any] = {},
    extractors: list[str] = [],
    use_recursive_directory_summarize: bool = False,
    pipeline_workers: int = 1,
):
    documents_path = config.documents_path

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
    
    trans.append(Settings.embed_model)
    
    # 设置Redis向量存储
    redis_client = Redis.from_url("redis://localhost:6379")
    redis_client.flushdb()
    custom_schema = IndexSchema.from_yaml(os.path.join(config.module_root_dir, "custom_schema.yaml"))
    
    vector_store = RedisVectorStore(
        redis_client=redis_client, schema=custom_schema, overwrite=True
    )

    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
    )
    nodes = pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)

    if os.path.exists(pipeline_cache_path):
        pipeline.load(pipeline_cache_path)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
    )
    nodes = pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)
    
    pipeline.persist(pipeline_cache_path)
    
    
def main():
    setup(add_system_prompt=True)
    new_documents=change_detect(config.data_dir)
    if args.load:
        load_and_index(
            new_documents=new_documents,
            pipeline_cache_path=str(config.pipeline_cache),
            text_spliter="sentence_splitter",
            text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
            extractors=[],
            use_recursive_directory_summarize=False,
            pipeline_workers=1,
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l", "--load",
        action="store_true",
        help="Call the load_and_index function if this option is set."
    )
    args = parser.parse_args()
    main()
