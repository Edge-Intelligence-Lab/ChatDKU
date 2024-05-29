#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document

import chromadb
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from settings import parse_args_and_setup


# Custom reader using the `unstructured` library.
# The `UnstructuredReader` provided by LlamaIndex has a issue with HTML files containing
# large amounts of JavaScript, which would be identified as having the MIME type of
# `application/javascript`, causing its use of `unstructured.partition.auto.partion` to
# wrongly identify the file type and not partition these files as HTML files.
#
# This reader supports `.html`, `.htm`, and `.pdf`.
# Modified from: https://github.com/run-llama/llama_index/blob/038d5105b684e5286b5771e7722ad3a9e3e8ec75/llama-index-integrations/readers/llama-index-readers-file/llama_index/readers/file/unstructured/base.py
class UnstructuredReader(BaseReader):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args)  # not passing kwargs to parent bc it cannot accept it

        # Prerequisite for Unstructured.io to work
        import nltk

        if not nltk.data.find("tokenizers/punkt"):
            nltk.download("punkt")
        if not nltk.data.find("taggers/averaged_perceptron_tagger"):
            nltk.download("averaged_perceptron_tagger")

    def load_data(
        self,
        file: Path,
        extra_info: Optional[Dict] = None,
        split_documents: Optional[bool] = False,
    ) -> List[Document]:
        if file.suffix == ".html" or file.suffix == ".htm":
            from unstructured.partition.html import partition_html

            elements = partition_html(filename=str(file))
        elif file.suffix == ".pdf":
            from unstructured.partition.pdf import partition_pdf

            elements = partition_pdf(filename=str(file))
        else:
            raise ValueError(f"Unsupported extension '{file.suffix}'")

        """ Process elements """
        docs = []
        if split_documents:
            for node in elements:
                metadata = {}
                if hasattr(node, "metadata"):
                    """Load metadata fields"""
                    for field, val in vars(node.metadata).items():
                        if field == "_known_field_names":
                            continue
                        # removing coordinates because it does not serialize
                        # and dont want to bother with it
                        if field == "coordinates":
                            continue
                        # removing bc it might cause interference
                        if field == "parent_id":
                            continue
                        metadata[field] = val

                if extra_info is not None:
                    metadata.update(extra_info)

                metadata["filename"] = str(file)
                docs.append(Document(text=node.text, extra_info=metadata))

        else:
            text_chunks = [" ".join(str(el).split()) for el in elements]

            metadata = {}

            if extra_info is not None:
                metadata.update(extra_info)

            metadata["filename"] = str(file)
            # Create a single document by joining all the texts
            docs.append(Document(text="\n\n".join(text_chunks), extra_info=metadata))

        return docs


def main():
    parse_args_and_setup()

    reader = UnstructuredReader()
    documents = SimpleDirectoryReader(
        "../RAG_data",
        recursive=True,
        required_exts=[".html", ".htm", ".pdf"],
        file_extractor={
            ".htm": reader,
            ".html": reader,
            ".pdf": reader,
        },
    ).load_data()

    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # TODO: Data loading could be customized either by supplying a list of custom
    # transformations or use transformation modules explicitly. The transformation
    # modules could be used standalone or composed in the ingestion pipeline.
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)


if __name__ == "__main__":
    main()
