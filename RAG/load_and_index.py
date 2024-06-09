#!/usr/bin/env python3

import os
import nltk
import chromadb
from llama_index.core import Settings, VectorStoreIndex, Document
from llama_index.readers.file import UnstructuredReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
from pathlib import Path
from settings import parse_args_and_setup

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
# import unstructured.partition.auto
# from custom_partation import partition

# unstructured.partition.auto.partition = partition


def extract_and_save_documents(data_dir, reader, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for root, _, files in os.walk(data_dir):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in [".html", ".htm", ".pdf", ".csv"]:
                documents = reader.load_data(file=file_path, split_documents=True)
                for i, doc in enumerate(documents):
                    output_file_path = Path(output_dir) / (file + f"_{i}.txt")
                    with open(output_file_path, "w", encoding="utf-8") as text_file:
                        text_file.write(doc.text)


def load_and_index(
    data_dir, text_spliter, text_spliter_args, pipeline_workers, output_dir
):
    nltk.download("averaged_perceptron_tagger")
    reader = UnstructuredReader()

    # Extract and save the documents using UnstructuredReader
    if not os.path.exists(output_dir):
        print("Create text_documents")
        extract_and_save_documents(data_dir, reader, output_dir)

    # Load documents from saved text files
    documents = []
    for root, _, files in os.walk(output_dir):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                doc_id = os.path.splitext(os.path.basename(file_path))[0]
                documents.append(Document(text=content, id=doc_id))

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
    pipeline_cache = "./pipeline_storage"
    if os.path.exists(pipeline_cache):
        pipeline.load(pipeline_cache)
    pipeline.run(documents=documents, num_workers=pipeline_workers)
    pipeline.persist(pipeline_cache)

    VectorStoreIndex.from_vector_store(vector_store)
    docstore.persist("./docstore")


def main():
    parse_args_and_setup()
    output_dir = "./extracted_docs"
    load_and_index(
        data_dir="../RAG_data",
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        pipeline_workers=1,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
