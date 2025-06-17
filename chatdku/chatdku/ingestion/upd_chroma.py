#!/usr/bin/env python3

import os
import shutil
import tempfile
import sys
import pickle
import chromadb
from typing import Any

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

def load_and_index(
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
    
    # Create a temporary directory in the same directory as config.chroma_db
    chroma_db_parent_dir = os.path.abspath(os.path.join(config.chroma_db, os.pardir))
    temp_chroma_db = tempfile.mkdtemp(dir=chroma_db_parent_dir, prefix='temp_chroma_db_')

    db = chromadb.PersistentClient(
        path=temp_chroma_db, settings=chromadb.Settings(allow_reset=True)
    )
    db.reset()
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    
    trans.append(Settings.embed_model)


    if os.path.exists(pipeline_cache_path):
        pipeline.load(pipeline_cache_path)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
    )
    nodes = pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)
    
    pipeline.persist(pipeline_cache_path)

    db.close()

    if os.path.exists(config.chroma_db):
        shutil.rmtree(config.chroma_db)
    os.rename(temp_chroma_db, config.chroma_db)
