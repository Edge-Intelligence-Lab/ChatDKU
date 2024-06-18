import os
import nltk
import pickle
import argparse
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import UnstructuredReader
from settings import Setting

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

def update_data(data_dir=None):
    
    if data_dir is None:
        data_dir=Setting.data_dir
    
    # Required for UnstructuredReader
    nltk.download("averaged_perceptron_tagger")
    reader = UnstructuredReader()

    documents_path = os.path.join(data_dir, "documents.pkl")

    reader = UnstructuredReader()
    documents = SimpleDirectoryReader(
        data_dir,
        recursive=True,
        required_exts=[".html", ".htm", ".pdf", ".csv"],
        file_extractor={
            ".htm": reader,
            ".html": reader,
            ".pdf": reader,
            ".csv": reader,
        },
    ).load_data()
    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)

    print("Length of documents:",len(documents))
    return documents

def main(data_dir=None):
    
    if data_dir is None:
        data_dir=Setting.data_dir

    update_data(data_dir)
    hash=hash_directory(data_dir)
    hash_path= os.path.join("./","hash.pkl")
    with open(hash_path, "wb") as hf:
        pickle.dump(hash,hf)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process data directory path")
    parser.add_argument('data_dir', type=str, help='The directory containing the data')
    args = parser.parse_args()

    main(args.data_dir)


