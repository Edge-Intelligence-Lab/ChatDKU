import os
import json
import nest_asyncio

import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.vector_stores.redis import RedisVectorStore
from redis import Redis
from redisvl.schema import IndexSchema
import uuid
import nltk
import hashlib
import pickle
from llama_index.core import SimpleDirectoryReader
from llama_parse import LlamaParse
from chatdku.config import config
from markdownify import markdownify as md
from chatdku.setup import setup
from chatdku.ingestion.load_chroma import load_chroma
from chatdku.ingestion.load_redis import load_redis

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

nest_asyncio.apply()
unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype
unstructured.partition.auto.partition = partition


def update(
    data_dir,
    user_id,
    reset: bool = False,
):
    setup(use_llm=False)

    result = update_documents(data_dir, user_id)

    # load chromadb
    load_chroma(
        documents=result["new documents"],
        data_dir=data_dir,
        reset=reset,
        pipeline_cache_path=str(config.pipeline_cache),
        text_spliter="sentence_splitter",
        text_spliter_args={"chunk_size": 1024, "chunk_overlap": 20},
        extractors=[],
        use_recursive_directory_summarize=False,
        pipeline_workers=1,
    )

    load_redis(
        documents=result["new documents"],
        reset=reset,
    )


def remove(
    data_dir,
    user_id,
):
    chroma_db = chromadb.PersistentClient(
        path=config.chroma_db, settings=chromadb.Settings(allow_reset=True)
    )

    chroma_collection = chroma_db.get_or_create_collection(config.chroma_collection)
    chroma_store = ChromaVectorStore(chroma_collection=chroma_collection)

    redis_client = Redis.from_url(config.redis_url)

    schema = IndexSchema.from_yaml(
        os.path.join(config.module_root_dir, "custom_schema.yaml")
    )

    redis_store = RedisVectorStore(
        redis_client=redis_client,
        schema=schema,
    )

    result = update_documents(data_dir, user_id)

    for id in result["deleted documents"]:
        chroma_store.delete(id)
        redis_store.delete(id)


def hash_file(filename):
    h = hashlib.sha256()
    with open(filename, "rb") as file:
        while True:
            chunk = file.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_directory(directory):
    all_hashes = ""
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            file_hash = hash_file(filepath)
            all_hashes += file_hash
    final_hash = hashlib.sha256(all_hashes.encode("utf-8")).hexdigest()
    return final_hash


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

    return {"added": added, "removed": removed, "modified": modified}


def update_documents(data_dir, user_id):
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

    changed_data = compare_directory_state(old_state, new_state)

    # Save changed data
    with open(output_file, "w") as f:
        json.dump(changed_data, f, indent=4)

    new_files = changed_data["added"] + changed_data["modified"]
    new_files = list(data_dir + "/" + new_file for new_file in new_files)
    timed_files = changed_data["modified"] + changed_data["removed"]
    timed_files = list(data_dir + "/" + timed_file for timed_file in timed_files)

    # Update documents
    documents_path = os.path.join(data_dir, "documents.pkl")
    # documents_path = config.documents_path
    # print(f"Current documents_path: {config.documents_path}")

    if not os.path.exists(documents_path):
        with open(documents_path, "wb") as f:
            pickle.dump([], f)

    with open(documents_path, "rb") as file:
        documents = pickle.load(file)
    print(f"Loaded documents from {documents_path}")

    # Remove deleted files from the DBs and the documents
    deleted_docs_id = []
    for document in documents:
        if document.metadata["file_path"] in timed_files:
            deleted_docs_id.append(document.doc_id)
            documents.remove(document)

    if len(new_files + timed_files) == 0:
        print("Nothing has changed")
    else:
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

    # Check and download required nltk packages
    try:
        nltk.data.find("taggers/averaged_perceptron_tagger_eng")
    except LookupError:
        nltk.download("averaged_perceptron_tagger_eng")

    try:
        nltk.data.find("taggers/averaged_perceptron_tagger")
    except LookupError:
        nltk.download("averaged_perceptron_tagger")

    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt")

    try:
        # NOTE: Just `nltk.data.find("tokenizers/punkt_tab")` won't work as LlamaIndex
        # replaces nltk tokenizers with its own version.
        nltk.data.find("tokenizers/punkt_tab/english")
    except LookupError:
        nltk.download("punkt_tab")

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

    # 二次过滤已解析的文件
    new_files = [file for file in new_files if file not in parsed_files]

    if len(new_files) != 0:
        for file in new_files:
            try:
                # Parse the file
                new_documents = SimpleDirectoryReader(
                    input_files=[file],
                    recursive=True,
                    required_exts=[".pdf"],
                    file_extractor={
                        ".pdf": pdf_parser,
                    },
                ).load_data()

                # FIXME: Mitigate the issue of  ,
                # which causes collision for files with the same filename.
                # See: https://github.com/run-llama/llama_index/issues/17144
                for doc in new_documents:
                    doc.doc_id = str(uuid.uuid4())

                    if doc.metadata["file_type"] == "text/html":
                        with open(doc.metadata["file_path"], "r") as f:
                            html = f.read()
                        try:
                            doc.text = md(html)
                        except:
                            print(f"fail trans to md:{doc.metadata['file_path']}")
                    doc.metadata["user_id"] = user_id

                # Update documents and save
                documents.extend(new_documents)
                with open(documents_path, "wb") as f:
                    pickle.dump(documents, f)

                # Update parsed files record and save
                parsed_files.add(file)
                with open(parsed_files_record, "wb") as f:
                    pickle.dump(parsed_files, f)
            except Exception as e:
                print(f"Error parsing {file}: {e}")
                # Optionally log the error to a file
                continue  # Proceed to the next file
    else:
        new_documents = []

    documents = documents + new_documents

    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)

    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=4)
    # 删除临时文件
    if os.path.exists(parsed_files_record):
        os.remove(parsed_files_record)

    print("Document successfully update")

    result = {"new documents": new_documents, "deleted documents": deleted_docs_id}

    return result
