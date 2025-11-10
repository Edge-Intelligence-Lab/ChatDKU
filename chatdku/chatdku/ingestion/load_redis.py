#!/usr/bin/env python3

from redis import Redis
from redisvl.schema import IndexSchema
from llama_index.vector_stores.redis import RedisVectorStore

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import TextNode

import os
import argparse
import json

######
from llama_index.core import Settings
from chatdku.setup import setup



from chatdku.config import config


def clean_file_name(file_name: str) -> str:
    return os.path.splitext(file_name)[0]


def load_redis(
    nodes: list[TextNode] = None,
    nodes_path: list = None,
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

    setup(use_llm=False)

    if nodes is None:
        if nodes_path is None:
            nodes_path = config.nodes_path
        print("Nodes path:", nodes_path)

        with open(nodes_path, "r") as f:
            datas = json.load(f)
        nodes = [TextNode.from_dict(data) for data in datas]

    for node in nodes:
        file_name = node.metadata["file_name"]
        node.metadata["file_name"] = clean_file_name(file_name)

    if index_name is None:
        index_name = config.index_name

    redis_client = Redis(
        host=config.redis_host,
        port=6379,
        username="default",
        password=config.redis_password,
    )

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
                {"type": "tag", "name": "user_id", "attrs": {"sortable": True}},
                {"type": "tag", "name": "doc_id"},
                {"type": "text", "name": "text"},
                {"type": "tag", "name": "file_name", "attrs": {"sortable": True}},
                {"type": "tag", "name": "page_number"},
                # Custom metadata fields
                {"type": "tag", "name": "groups"},
                {"type": "tag", "name": "file_path", "attrs": {"sortable": True}},
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
    pipeline = IngestionPipeline(
        vector_store=vector_store, transformations=[Settings.embed_model]
    )
    if os.path.exists(pipeline_cache_path):
        pipeline.load(pipeline_cache_path)
    pipeline.run(nodes=nodes, num_workers=pipeline_workers, show_progress=True)

    print("Redis load done!")


def main(nodes_path, index_name, reset):
    # with open(nodes_path, "rb") as f:
    #     documents = pickle.load(f)

    load_redis(
        nodes_path=nodes_path,
        index_name=index_name,
        pipeline_cache_path=str(config.pipeline_cache),
        reset=reset,
    )


def str2bool(val):
    if isinstance(val, bool):
        return val
    if val.lower() in ["t", "true"]:
        return True
    if val.lower() in ["f", "false"]:
        return False
    else:
        raise ValueError(f"Expected String, got {type(val)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load the specified nodes.json file into redis"
    )
    parser.add_argument(
        "--nodes_path",
        type=str,
        default=config.nodes_path,
        help="The directory containing the data",
    )
    parser.add_argument(
        "--index_name",
        type=str,
        default=config.index_name,
        help="Name of the Redis index.",
    )
    parser.add_argument(
        "--reset",
        type=str2bool,
        default=False,
        help="Overwrite existing data?",
    )
    args = parser.parse_args()

    main(args.nodes_path, args.index_name, args.reset)
