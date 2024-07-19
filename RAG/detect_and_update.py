import os
import pickle
import json
import chromadb
import hashlib
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.readers.file import UnstructuredReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_parse import LlamaParse

from settings import setup
from config import Config

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition

def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
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
    changes = {
        'added': added,
        'removed': removed,
        'modified': modified
    }
    if os.path.exists(output_file):
        with open(output_file, 'w') as f:
            json.dump(changes, f, indent=4)

def change_detect(data_dir):

    output_file="changed_data.json"
    state_file="data_state.json"

    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            old_state = json.load(f)
    else:
        old_state = {}

    new_state = record_directory_state(data_dir)

    added, removed, modified = compare_directory_state(old_state, new_state)

    export_changes(added, removed, modified, output_file)
    
    with open(state_file, 'w') as f:
        json.dump(new_state, f, indent=4)

def change_update(
        data_dir,
        pipeline_cache_path,
        pipeline_workers,
        use_recursive_directory_summarize: bool = False,
        extractors: list[str] = [],
        text_spliter: str = "sentence_splitter",
        text_spliter_args: dict[str, Any] = {},
    ):

    output_file="changed_data.json"
    reader = UnstructuredReader()
    llama_parse_api_key = "llx-dwGAqjLq7SqCXu7u9y2lBDyyIlnVvbh0pSJUed1toAsnwseQ"
    pdf_parser = LlamaParse(
        api_key=llama_parse_api_key, 
        result_type="markdown",
        verbose=True,
    )

    #Load changed data
    with open(output_file, 'r') as f:
        changed_data=json.load(f)
    
    new_files=changed_data["added"]+changed_data["modified"]
    new_files=list(data_dir+'/'+new_file for new_file in new_files)
    timed_files=changed_data["modified"]+changed_data["removed"]  
    timed_files=list(data_dir+'/'+timed_file for timed_file in timed_files)   
    
    #If no data_update
    if len(new_files+timed_files) == 0:
        print("Nothing has changed")
        return
    
    print("Added",len(changed_data["added"]),"documents\n",
          "Modified",len(changed_data["modified"]),"documents\n",
          "Removed",len(changed_data["removed"]),"documents\n")
    
    #Update documents
    documents_path = os.path.join(data_dir, "new_parser_documents.pkl")
    with open(documents_path, "rb") as file:
        documents = pickle.load(file)
    print(f"Loaded documents from {documents_path}")

    for document in documents:
        if document.metadata["file_path"] in timed_files:
            documents.remove(document)
  
    new_documents=SimpleDirectoryReader(
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

    documents=documents+new_documents
    
    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)

    print("Document successfully update")
    
    #Prepare chromadb and ingestion pipeline
    db = chromadb.PersistentClient(
            path=Config.vector_store_path, settings=chromadb.Settings(allow_reset=True)
        )
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

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


    pipeline = IngestionPipeline(
        transformations=trans,
        vector_store=vector_store,
    )
    if os.path.exists(pipeline_cache_path):
        pipeline.load(pipeline_cache_path)


    #Nodes and Vector_store Delete
    docs=chroma_collection.get()
    deleted_nodes=[]#这是等下要用到的米奇妙妙工具
    num_docs=len(docs["metadatas"])
    print(num_docs)
    for i in range(num_docs):
        doc_path=json.loads(docs["metadatas"][i]['_node_content'])["metadata"]["file_path"]
        if doc_path in timed_files:
            chroma_collection.delete(ids=[docs["ids"][i]])
            deleted_doc_id=docs["metadadas"][i]["doc_id"]
            if deleted_doc_id not in deleted_nodes:
                deleted_nodes.append(deleted_doc_id)

    #Vector_store Update
    #还是跑全部documents吧，毕竟cache不会同步
    new_nodes = pipeline.run(
        documents=documents, num_workers=pipeline_workers, show_progress=True
    )
    pipeline.persist(pipeline_cache_path)

    print("ChromaDB successfully update")

    #Update docstore
    docstore = SimpleDocumentStore.from_persist_path(Config.docstore_path)
    for deleted_node in deleted_nodes:
        docstore.delete_document(deleted_node)
    
    docstore.add_documents(new_nodes)
    docstore.persist(Config.docstore_path)

    print("Docstore successfully update")

    print("--FINISH--")

def main():
    setup()
    config=Config()

    change_detect(data_dir=str(config.data_dir))

    change_update(data_dir=str(config.data_dir),
            pipeline_cache_path=str(config.pipeline_cache),
            pipeline_workers=1,
            text_spliter="sentence_splitter",
            text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},)

if __name__ == "__main__":
    main()
