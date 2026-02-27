#!/usr/bin/env python3

# import os
import json
import chromadb
import argparse
from chromadb.utils.embedding_functions import HuggingFaceEmbeddingServer

# from llama_index.core import Settings
# from llama_index.vector_stores.chroma import ChromaVectorStore
# from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import TextNode

# from chatdku.setup import setup
from chatdku.config import config


def nodes_to_dicts(nodes: list):
    result = {
        "ids": [],
        "texts": [],
        "metadatas": [],
    }
    for node in nodes:
        if not node.text or not isinstance(node.text, str):
            continue
        result["ids"].append(node.node_id)
        result["texts"].append(node.text)
        result["metadatas"].append(node.metadata)

    return result


def load_chroma(
    collection: str = None,
    nodes_path=None,
    reset: bool = False,
    buffer_size: int = 25,
):
    """
    Populate the ChromaDB. If you run this from the terminal it will re-populate
    the ChromaDB from the start. If you import the function load_chroma(), you can add documents
    without resetting Redis.

    documents: It will accept Llamaindex documents (files ending with .pkl).
        If you leave it out, it will take documents from config.documents_path.
        You can fill this in to add documents to redis.
    collection: You can set this to any other name to create another collection in chromaDB but
        for Redis.
    reset: Whether to overwrite the data already on the DB.
    """
    if nodes_path is None:
        nodes_path = config.nodes_path

    print("Nodes path:", nodes_path)
    with open(nodes_path, "r") as f:
        datas = json.load(f)
    nodes = [TextNode.from_dict(data) for data in datas]
    if collection is None:
        collection = config.user_uploads_collection
    print("Collection: ", collection)

    chroma_db = chromadb.HttpClient(
        host=config.chroma_host, port=config.chroma_db_port
    )

    if reset:
        for col in chroma_db.list_collections():
            if collection == col.name:
                print(f"Deleting collection {collection}")
                chroma_db.delete_collection(
                    collection
                )  # Clear previously stored data in vector database

    collection = chroma_db.get_or_create_collection(
        name=collection,
        embedding_function=HuggingFaceEmbeddingServer(
            url=f"{config.tei_url}/{config.embedding}/embed"
        ),
        metadata={
            "hnsw:batch_size": 512,
            "hnsw:sync_threshold": 1024,
        },
    )
    nodes_buffer = []
    for i, node in enumerate(nodes):
        nodes_buffer.append(node)

        if i % buffer_size == 0:
            nodes_buffer_dict = nodes_to_dicts(nodes_buffer)
            try:
                collection.add(
                    ids=nodes_buffer_dict["ids"],
                    documents=nodes_buffer_dict["texts"],
                    metadatas=nodes_buffer_dict["metadatas"],
                )
            except Exception as e:
                for i in nodes_buffer_dict["metadatas"]:
                    print(i)
                raise e
                for node in nodes_buffer:
                    node_dict = nodes_to_dicts(node)
                    try:
                        collection.add(
                            ids=node_dict["ids"],
                            documents=node_dict["texts"],
                            metadatas=node_dict["metadatas"],
                        )

                    except Exception as e:
                        raise e
            nodes_buffer = []

    if nodes_buffer:
        nodes_buffer_dict = nodes_to_dicts(nodes_buffer)
        try:
            collection.add(
                ids=nodes_buffer_dict["ids"],
                documents=nodes_buffer_dict["texts"],
                metadatas=nodes_buffer_dict["metadatas"],
            )
        except Exception as e:
            raise e
            for node in nodes_buffer:
                node_dict = nodes_to_dicts(node)
                try:
                    collection.add(
                        ids=node_dict["ids"],
                        documents=node_dict["texts"],
                        metadatas=node_dict["metadatas"],
                    )

                except Exception as e:
                    raise e

    # NOTE: Currently, LlamaIndex has bug with using both caching and docstore.
    # I am using only caching here and there is not much need for attaching a
    # docstore for deduplication anyways.
    # See https://github.com/run-llama/llama_index/issues/14068 for details.
    # pipeline = IngestionPipeline(
    #     transformations=trans,
    #     vector_store=vector_store,
    # )
    # if os.path.exists(pipeline_cache_path):
    #     pipeline.load(pipeline_cache_path)
    #
    # pipeline.run(documents=documents, num_workers=pipeline_workers, show_progress=True)
    #
    # nodes = pipeline.run(
    #     documents=documents, num_workers=pipeline_workers, show_progress=True
    # )
    # pipeline.persist(pipeline_cache_path)
    print("Chroma load done!")
    #
    # docstore = SimpleDocumentStore()
    # docstore.add_documents(nodes)
    # docstore.persist(config.docstore_path)
    # print("docstore over")


def main(nodes_path=None, collection_name=None):
    load_chroma(
        reset=False,
        nodes_path=nodes_path,
        collection=collection_name,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load the specified .pkl file into chroma."
    )
    parser.add_argument(
        "--nodes_path",
        type=str,
        default=config.nodes_path,
        help="The directory containing the data",
    )
    parser.add_argument(
        "--collection_name",
        type=str,
        default=config.chroma_collection,
        help="Name of the chroma collection.",
    )
    args = parser.parse_args()

    main(args.nodes_path, args.collection_name)
