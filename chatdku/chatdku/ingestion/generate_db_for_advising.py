import os
import chromadb
import ollama
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredHTMLLoader,
)

import os
import chromadb
from tqdm import tqdm

db_path = "/datapool/db_chat_dku_advising_test"
os.makedirs(db_path, exist_ok=True) 

client = chromadb.PersistentClient(path=db_path)

text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\n\n",
        "\n",
        ".",
        ",",
        "\u200b",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
        "?",
    ],
    chunk_size=512,
    chunk_overlap=20,
    length_function=len,
    is_separator_regex=False,
)

EMBEDDING_MODEL = "bge-m3"

collection = client.get_or_create_collection("vectorDB")


def add_chunk(chunk, filename, page=0):
    embedding = ollama.embed(model=EMBEDDING_MODEL, input=chunk)["embeddings"][0]
    collection.add(
        documents=[chunk],
        embeddings=[embedding],
        ids=(str(hash(chunk))),
        metadatas=[{"filename": filename, "page": page}],
    )


def read_files(path):
    print(f"Reading from directory: {os.path.abspath(path)}")
    if not os.path.exists(path):
        print(f"Error: The directory '{path}' does not exist.")
        return

    existing_files = []
    with open("/home/Glitterccc/CODESSSS/ChatDKU-chat_dku_student_release/chatdku/chatdku/ingestion/.FilesAdded.txt", "r") as file:
        for line in file:
            existing_files.append(line.strip())

    log = open("/home/Glitterccc/CODESSSS/ChatDKU-chat_dku_student_release/chatdku/chatdku/ingestion/.FilesAdded.txt", "a")
    for filename in tqdm(os.listdir(path)):
        if filename == ".FilesAdded.txt" or filename in existing_files:
            continue
        file_path = os.path.join(path, filename)

        print(f"Processing file: {file_path}")

        # ----- PDF 文件 -----
        if filename.endswith(".pdf"):
            pdf_loader = PyPDFLoader(file_path)
            for page in pdf_loader.load():
                entry = text_splitter.split_text(page.page_content)
                for chunk in entry:
                    add_chunk(chunk, filename, page.metadata.get("page", 0))

        # ----- HTML 文件 -----
        elif filename.endswith(".html") or filename.endswith(".htm"):
            html_loader = UnstructuredHTMLLoader(file_path)
            docs = html_loader.load()
            for doc in docs:
                entry = text_splitter.split_text(doc.page_content)
                for chunk in entry:
                    add_chunk(chunk, filename)


        log.write(filename + "\n")
        print(f"Finished loading {filename}.")
    log.close()


read_files("/datapool/chat_dku_advising")

print("Finished adding all files to vector database.")
