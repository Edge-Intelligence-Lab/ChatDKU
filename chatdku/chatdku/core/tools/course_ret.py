"""
Course retriever
Written by: Temuulen
"""

import re

import chromadb
from chromadb.utils.embedding_functions import HuggingFaceEmbeddingServer
from llama_index.core.schema import NodeWithScore, TextNode

from chatdku.config import config


def chroma_result_to_nodes(result: dict) -> list[NodeWithScore]:
    ids = result["ids"][0]
    texts = result["documents"][0]
    metadatas = result["metadatas"][0]
    scores = result["distances"][0]

    return [
        NodeWithScore(
            node=TextNode(
                node_id=ids[i],
                text=texts[i],
                metadata={
                    "file_name": metadatas[i].get("file_name", "Not given."),
                    # HACK: Hardcoded URL for now
                    "url": "https://duke.box.com/s/4qez9bss1vjmkccn2rcqbhphcmh9wpxs",
                },
            ),
            score=float(scores[i]),
        )
        for i in range(len(ids))
    ]


def nodes_to_dicts(nodes: list[NodeWithScore]) -> list:
    result = []
    for node in nodes:
        if isinstance(node, NodeWithScore):
            result.append([{"text": node.text, "metadata": node.metadata}])
        if isinstance(node, str):
            result.append(node)
    return result


def course_retriever(course_queries: list[str]) -> list[dict]:
    """
    Retrieve courses from ChromaDB using semantic search or metadata filtering.

    Automatically detects course code patterns (e.g., "COMPSCI 101", "BIO 111")
    and applies metadata filtering for exact matches. Text-based queries use
    semantic search via embeddings.

    Will return course descriptions, prerequisites, course code, as well as
    in which page the course is located in the student bulletin.

    Args:
        course_queries (list[str]): List of search queries. Can be course codes
            in format "DEPT NNN" (e.g. "BEHAVSCI 102", "COMPSCI 101") or natural language
            queries (e.g., "introduction programming course"). You can also mix
            course codes and natural language queries.

    Returns:
        list[dict]: Query results from ChromaDB collection. Each result contains
            matched documents with their metadata, embeddings, and distances.
            Results are combined from both metadata-filtered and semantic searches.

    Examples:
        >>> course_retriever(["COMPSCI 101"])
        # Uses metadata filtering for exact course code match

        >>> course_retriever(["machine learning courses"])
        # Uses semantic search across course descriptions

        >>> course_retriever(["BIO 111", "introduction to chemistry"])
        # Combines metadata filtering for BIO 111 with semantic search
    """
    db = chromadb.HttpClient(host="localhost", port=config.chroma_db_port)
    collection = db.get_collection(
        name=config.courses_col,
        embedding_function=HuggingFaceEmbeddingServer(
            url=config.tei_url + "/" + config.embedding + "/embed"
        ),
    )

    # Pattern to match course codes like "COMPSCI 101" or "BIO 111"
    course_code_pattern = re.compile(r"^[A-Z]+\s+\d+$", re.IGNORECASE)

    # Separate queries into course codes and text queries
    course_codes = []
    text_queries = []

    for query in course_queries:
        if course_code_pattern.match(query.strip()):
            course_codes.append(query.strip())
        else:
            text_queries.append(query)

    total = []
    # If all queries are course codes, use metadata filtering
    if course_codes:
        for course_code in course_codes:
            where_filter = {"course_code": course_code}

            chroma_result = collection.query(
                query_texts=course_code,
                n_results=1,
                where=where_filter,
            )

            total.extend(chroma_result_to_nodes(chroma_result))

    if text_queries:
        chroma_result = collection.query(
            query_texts=text_queries,
            n_results=3,
        )
        total.extend(chroma_result_to_nodes(chroma_result))

    nodes = nodes_to_dicts(total)
    internal_result = {
        "ids": {node.node_id for node in total if isinstance(node, NodeWithScore)}
    }
    return nodes, internal_result
