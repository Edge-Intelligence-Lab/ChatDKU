from llama_index.core.schema import TextNode
from redis import Redis
from redisvl.schema import IndexSchema
from llama_index.vector_stores.redis import RedisVectorStore

from llama_index.embeddings.text_embeddings_inference import TextEmbeddingsInference
from llama_index.core.ingestion import IngestionPipeline

import pickle


######
from pathlib import Path
import pickle
import chromadb
from llama_index.core import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import IngestionPipeline
from typing import Any
from chatdku.setup import setup
from update_data import update_data, hash_directory

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition

from chatdku.config import config

setup(add_system_prompt=True)


with open("/home/Glitterccc/ChatDKU/documents/chatdku_documents_2.pkl", "rb") as f:
    documents = pickle.load(f)


redis_client = Redis.from_url("redis://localhost:6379")

custom_schema = IndexSchema.from_dict(
    {
        "index": {
            "name": "idx:test",
            "prefix": "test_doc",
            "key_separator": ":",
        },
        "fields": [
            # Required fields for llamaindex
            {"type": "tag", "name": "id"},
            {"type": "tag", "name": "user_id"},
            {"type": "tag", "name": "doc_id"},
            {"type": "text", "name": "text"},
            # Custom metadata fields
            {"type": "tag", "name": "groups"},
            {"type": "tag", "name": "file_path"},
            {"type": "tag", "name": "file_name"},
            {"type": "tag", "name": "last_modified_date"},
            # Custom vector embeddings field definition
            {
                "type": "vector",
                "name": "vector",
                "attrs": {
                    # NOTE: This should match the size of the vector embeddings
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

# embed_model = TextEmbeddingsInference(
#     model_name="BAAI/bge-m3",
#     base_url="http://localhost:18080/BAAI/bge-m3",
# )


trans = []

extractors = []
text_spliter = "sentence_splitter"
use_recursive_directory_summarize = False
text_spliter_args = {"chunk_size": 1024, "chunk_overlap": 20}


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
nodes = pipeline.run(documents=documents, num_workers=1, show_progress=True)
