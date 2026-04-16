"""Tests for chatdku.core.tools.llama_index_tools (VectorRetrieverOuter, KeywordRetrieverOuter)."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from chatdku.core.tools.retriever.base_retriever import NodeWithScore
from chatdku.core.tools.utils import QueryTimeoutError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_NODES = [
    NodeWithScore(node_id="1", text="doc one", metadata={"src": "a"}, score=0.9),
    NodeWithScore(node_id="2", text="doc two", metadata={"src": "b"}, score=0.8),
]


@contextmanager
def fake_timeout(seconds=5):
    """Drop-in replacement for the real timeout context manager."""

    class FakeCtx:
        def run(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    yield FakeCtx()


@contextmanager
def fake_timeout_that_expires(seconds=5):
    """Simulates a timeout by raising QueryTimeoutError on .run()."""

    class FakeCtx:
        def run(self, func, *args, **kwargs):
            raise QueryTimeoutError(f"Query exceeded {seconds} second timeout")

    yield FakeCtx()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _patch_vector_retriever(monkeypatch):
    """Patch VectorRetriever class so no ChromaDB connection is needed."""
    mock_instance = MagicMock()
    mock_instance.query_with_tell.return_value = SAMPLE_NODES
    mock_cls = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(
        "chatdku.core.tools.llama_index_tools.VectorRetriever", mock_cls
    )
    return mock_instance


@pytest.fixture()
def _patch_keyword_retriever(monkeypatch):
    """Patch KeywordRetriever class so no Redis connection is needed."""
    mock_instance = MagicMock()
    mock_instance.query_with_tell.return_value = SAMPLE_NODES
    mock_cls = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(
        "chatdku.core.tools.llama_index_tools.KeywordRetriever", mock_cls
    )
    return mock_instance


@pytest.fixture()
def _patch_rerank(monkeypatch):
    """Patch the rerank function."""
    mock_rerank = MagicMock(return_value=SAMPLE_NODES[:1])
    monkeypatch.setattr("chatdku.core.tools.llama_index_tools.rerank", mock_rerank)
    return mock_rerank


@pytest.fixture()
def _patch_timeout(monkeypatch):
    """Replace the real timeout with a synchronous fake."""
    monkeypatch.setattr("chatdku.core.tools.llama_index_tools.timeout", fake_timeout)


@pytest.fixture()
def _patch_timeout_expires(monkeypatch):
    """Replace the real timeout with one that always times out."""
    monkeypatch.setattr(
        "chatdku.core.tools.llama_index_tools.timeout", fake_timeout_that_expires
    )


# ---------------------------------------------------------------------------
# VectorRetrieverOuter
# ---------------------------------------------------------------------------


class TestVectorRetrieverOuter:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        mock_get_current_span,
        _patch_vector_retriever,
        _patch_rerank,
        _patch_timeout,
    ):
        self.mock_retriever = _patch_vector_retriever
        self.mock_rerank = _patch_rerank

    def _make(self, **kwargs):
        from chatdku.core.tools.llama_index_tools import VectorRetrieverOuter

        defaults = dict(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id="Chat_DKU",
            search_mode=0,
            files=[],
        )
        defaults.update(kwargs)
        return VectorRetrieverOuter(**defaults)

    def test_returns_callable(self):
        assert callable(self._make())

    def test_query_returns_string(self):
        fn = self._make()
        result = fn("what is DKU?")
        assert isinstance(result, str)

    def test_query_calls_retriever(self):
        fn = self._make()
        fn("what is DKU?")
        self.mock_retriever.query_with_tell.assert_called_once()

    def test_with_reranker_calls_rerank(self):
        fn = self._make(use_reranker=True)
        fn("what is DKU?")
        self.mock_rerank.assert_called_once()

    def test_without_reranker_skips_rerank(self):
        fn = self._make(use_reranker=False)
        fn("what is DKU?")
        self.mock_rerank.assert_not_called()

    def test_invalid_search_mode_defaults_to_zero(self):
        # Should not raise; logs a warning and defaults to 0
        fn = self._make(search_mode=5)
        result = fn("test")
        assert isinstance(result, str)

    def test_search_mode_nonzero_without_files_defaults(self):
        # search_mode=1 but files=[] → should default to 0
        fn = self._make(search_mode=1, files=[])
        result = fn("test")
        assert isinstance(result, str)

    def test_value_error_propagates(self):
        self.mock_retriever.query_with_tell.side_effect = ValueError("bad input")
        fn = self._make()
        with pytest.raises(ValueError, match="bad input"):
            fn("test")

    def test_retrieval_failure_raises_exception(self):
        self.mock_retriever.query_with_tell.side_effect = RuntimeError(
            "connection lost"
        )
        fn = self._make()
        with pytest.raises(Exception, match="Vector retrieval failed"):
            fn("test")


class TestVectorRetrieverOuterTimeout:
    def test_timeout_raises_exception(
        self,
        mock_get_current_span,
        _patch_vector_retriever,
        _patch_rerank,
        _patch_timeout_expires,
    ):
        from chatdku.core.tools.llama_index_tools import VectorRetrieverOuter

        fn = VectorRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id="Chat_DKU",
            search_mode=0,
            files=[],
        )
        with pytest.raises(Exception, match="timed out"):
            fn("test")


# ---------------------------------------------------------------------------
# KeywordRetrieverOuter
# ---------------------------------------------------------------------------


class TestKeywordRetrieverOuter:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        mock_get_current_span,
        _patch_keyword_retriever,
        _patch_rerank,
        _patch_timeout,
    ):
        self.mock_retriever = _patch_keyword_retriever
        self.mock_rerank = _patch_rerank

    def _make(self, **kwargs):
        from chatdku.core.tools.llama_index_tools import KeywordRetrieverOuter

        defaults = dict(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id="Chat_DKU",
            search_mode=0,
            files=[],
        )
        defaults.update(kwargs)
        return KeywordRetrieverOuter(**defaults)

    def test_returns_callable(self):
        assert callable(self._make())

    def test_query_string_returns_string(self):
        fn = self._make()
        result = fn("DKU courses")
        assert isinstance(result, str)

    def test_query_list_converts_to_strings(self):
        fn = self._make()
        result = fn(["term1", 42, "term3"])
        assert isinstance(result, str)
        # The function stringifies list items in-place
        self.mock_retriever.query_with_tell.assert_called_once()

    def test_query_calls_retriever(self):
        fn = self._make()
        fn("test query")
        self.mock_retriever.query_with_tell.assert_called_once()

    def test_with_reranker_calls_rerank(self):
        fn = self._make(use_reranker=True)
        fn("test")
        self.mock_rerank.assert_called_once()

    def test_without_reranker_skips_rerank(self):
        fn = self._make(use_reranker=False)
        fn("test")
        self.mock_rerank.assert_not_called()

    def test_invalid_search_mode_defaults_to_zero(self):
        fn = self._make(search_mode=5)
        result = fn("test")
        assert isinstance(result, str)

    def test_retrieval_failure_raises_exception(self):
        self.mock_retriever.query_with_tell.side_effect = RuntimeError("redis down")
        fn = self._make()
        with pytest.raises(Exception, match="Keyword retrieval failed"):
            fn("test")


class TestKeywordRetrieverOuterTimeout:
    def test_timeout_raises_exception(
        self,
        mock_get_current_span,
        _patch_keyword_retriever,
        _patch_rerank,
        _patch_timeout_expires,
    ):
        from chatdku.core.tools.llama_index_tools import KeywordRetrieverOuter

        fn = KeywordRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id="Chat_DKU",
            search_mode=0,
            files=[],
        )
        with pytest.raises(Exception, match="Keyword retriever timeout"):
            fn("test")
