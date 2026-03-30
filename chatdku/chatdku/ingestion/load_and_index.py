"""
Main ingestion pipeline for loading and indexing documents.
Uses cached documents from update_data() and processes them through
LlamaIndex transformations before storing in vector database.
"""

import os
import pickle
import chromadb
from llama_index.core import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
from typing import Any
from chatdku.setup import setup
from update_data import update_data, hash_directory
from chatdku.config import config
# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partition
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition


def load_and_index(
    update: bool,
    read_only: bool,
    data_dir: str,
    pipeline_cache_path: str,
    text_spliter: str = "sentence_splitter",
    text_spliter_args: dict[str, Any] = {},
    extractors: list[str] = [],
    use_recursive_directory_summarize: bool = False,
    pipeline_workers: int = 1,
):
    documents_path = os.path.join(config.data_dir, config.documents_path)
    hash_path = os.path.join("./", "hash.pkl")
    now_hash = hash_directory(data_dir)
    
    if update:
        documents = update_data(data_dir)
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
                documents = update_data(data_dir)
                now_hash = hash_directory(data_dir)
                with open(hash_path, "wb") as hf:
                    pickle.dump(now_hash, hf)
    
    else:
        documents = update_data(data_dir)
        now_hash = hash_directory(data_dir)
        with open(hash_path, "wb") as hf:
            pickle.dump(now_hash, hf)
    
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
    
    # Note: SentenceSplitter is NOT applied to PDF documents because:
    #   1. PDF documents are already chunked during update_data()
    #   2. They have metadata {"chunking_method": "structure_aware"}
    #   3. Applying SentenceSplitter would corrupt the structure
    
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
    db.reset()
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
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
    setup(add_system_prompt=True)
    
    load_and_index(
        update=False,
        read_only=False,
        data_dir=str(config.data_dir),
        pipeline_cache_path=str(config.pipeline_cache),
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        extractors=[],
        use_recursive_directory_summarize=False,
        pipeline_workers=1,
    )


if __name__ == "__main__":
    main()
