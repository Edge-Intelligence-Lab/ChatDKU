import time

import pytest

from chatdku.core.tools.llama_index import (
    KeywordRetrieverOuter,
    QueryTimeoutError,
    VectorRetrieverOuter,
    timeout,
)
from chatdku.setup import setup, use_phoenix

setup()
use_phoenix()
vector_retriever = VectorRetrieverOuter(retriever_top_k=10, use_reranker=False)
keyword_retriever = KeywordRetrieverOuter(retriever_top_k=10, use_reranker=False)


def test_valid_queries():
    assert len(vector_retriever("How often should I visit my advisor?")) == 10
    assert len(keyword_retriever("COMPSCI")) == 10
    assert len(keyword_retriever(["COMPSCI", "ARTS AND MEDIA"])) == 10


def test_vector_time():
    """Test for response time with varying sizes of queries"""
    SEMANTIC_QUERIES = [
        "hello",
        "How often should I visit my advisor?",
        "What are the courses of Applied Mathematics",
        """The professor sent me this as requirement to be my SW mentor:
        Please send me your CV and transcript.
        In particular, please send me your planned proposal draft and try your best to answer the following:
        Research topic and key question,
        Existing works and their limitation,
        Your Idea and workplan
        Once I received the above, I will schedule an in-person meeting with you.
        Thanks. ;
        What do I need to do?
        """,
    ]

    for i, query in enumerate(SEMANTIC_QUERIES):

        start_time = time.time()
        results = vector_retriever(query)
        elapsed = time.time() - start_time

        print(
            f"Query {i+1}: {elapsed:.2f}s - {'TIMEOUT' if not results else f'{len(results)} results'}"
        )

        # Assert that query completed within timeout
        assert elapsed < 6.0, f"Query {i+1} took {elapsed:.2f}s (expected < 6s)"


def test_response_time():
    """Test for response time with varying sizes of queries"""
    KEYWORD_QUERIES = [
        "COMPSCI",
        "machine learning courses",
        "what is compsci 3065 about?",
        """The professor sent me this as requirement to be my SW mentor:
        Please send me your CV and transcript.
        In particular, please send me your planned proposal draft and try your best to answer the following:
        Research topic and key question,
        Existing works and their limitation,
        Your Idea and workplan
        Once I received the above, I will schedule an in-person meeting with you.
        Thanks. ;
        What do I need to do?
        """,
    ]

    for i, query in enumerate(KEYWORD_QUERIES):
        start_time = time.time()
        results = keyword_retriever(query)
        elapsed = time.time() - start_time

        print(
            f"Query {i+1}: {elapsed:.2f}s - {'TIMEOUT' if not results else f'{len(results)} results'}"
        )

        # Assert that query completed within timeout
        assert elapsed < 6.0, f"Query {i+1} took {elapsed:.2f}s (expected < 6s)"


def test_timeout_mechanism():
    """Verify that the timeout actually stops long-running queries"""
    with pytest.raises(QueryTimeoutError):
        with timeout(2) as ctx:
            ctx.run(time.sleep, 5)
