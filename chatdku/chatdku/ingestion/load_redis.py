from redis import Redis
from redisvl.schema import IndexSchema
from llama_index.vector_stores.redis import RedisVectorStore

from llama_index.core.ingestion import IngestionPipeline

import pickle
import os
import argparse

######
from llama_index.core import Settings
from chatdku.setup import setup

# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from chatdku.ingestion.custom_filetype_detect import custom_detect_filetype


# Override auto partation
import unstructured.partition.auto
from chatdku.ingestion.custom_partation import partition
from chatdku.config import config

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype
unstructured.partition.auto.partition = partition


def load_redis(
    documents=None,
    index_name: str = None,
    pipeline_workers: int = 1,
    pipeline_cache_path: str = config.pipeline_cache,
    reset: bool = False,
):
    """
    Populate the Redis. If you run this from the terminal it will re-populate
    the Redis from the start. If you import the function load_redis(), you can
    add documents without resetting Redis.

    documents: It will accept Llamaindex documents (files ending with .pkl).
        If you leave it out, it will take documents from config.documents_path.
        You can fill this in to add documents to redis.
    index_name: You can set this to any other name to act as if creating
        another collection in chromaDB but for Redis.
    reset: Whether to overwrite the data on the existing DB.
    """

    if documents is None:
        with open(config.documents_path, "rb") as f:
            documents = pickle.load(f)

    if index_name is None:
        index_name = config.index_name

    redis_client = Redis.from_url(config.redis_url)

    custom_schema = IndexSchema.from_dict(
        {
            "index": {
                "name": f"idx:{index_name}",
                "prefix": f"{index_name}_doc",
                "key_separator": ":",
            },
            "fields": [
                # Required fields for llamaindex
                {"type": "tag", "name": "id"},
                {"type": "tag", "name": "user_id"},
                {"type": "tag", "name": "doc_id"},
                {"type": "text", "name": "text"},
                {"type": "tag", "name": "file_name"},
                # Custom metadata fields
                {"type": "tag", "name": "groups"},
                {"type": "tag", "name": "file_path"},
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

    custom_schema.to_yaml(os.path.join(config.module_root_dir, "custom_schema.yaml"))

    vector_store = RedisVectorStore(
        redis_client=redis_client, schema=custom_schema, overwrite=reset
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

    if os.path.exists(pipeline_cache_path):
        pipeline.load(pipeline_cache_path)

    pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)


def main(documents_path, index_name):
    setup(use_llm=False)

    with open(documents_path, "rb") as f:
        documents = pickle.load(f)

    load_redis(
        documents=documents,
        index_name=index_name,
        pipeline_cache_path=str(config.pipeline_cache),
        reset=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load the specified .pkl file into redis"
    )
    parser.add_argument(
        "--documents_path",
        type=str,
        default=config.documents_path,
        help="The directory containing the data",
    )
    parser.add_argument(
        "--index_name",
        type=str,
        default=config.index_name,
        help="Name of the Redis index.",
    )
    args = parser.parse_args()

    main(args.documents_path, args.index_name)
