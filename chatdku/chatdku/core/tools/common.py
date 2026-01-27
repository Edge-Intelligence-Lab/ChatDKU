import os
import re
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from enum import Enum
from typing import Any

import pandas as pd
from chromadb.api.types import QueryResult
from llama_index.core.schema import NodeWithScore, TextNode
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import DocumentAttributes, SpanAttributes
from opentelemetry.util.types import AttributeValue

from chatdku.config import config


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the timeout limit."""

    pass


@contextmanager
def timeout(seconds: int = 5):
    """Thread-safe timeout using concurrent.futures."""

    class TimeoutContext:
        def __init__(self):
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.future = None

        def run(self, func, *args, **kwargs):
            self.future = self.executor.submit(func, *args, **kwargs)
            try:
                return self.future.result(timeout=seconds)
            except FuturesTimeoutError:
                raise QueryTimeoutError(f"Query exceeded {seconds} second timeout")
            finally:
                self.executor.shutdown(wait=False)

    ctx = TimeoutContext()
    try:
        yield ctx
    finally:
        if ctx.executor:
            ctx.executor.shutdown(wait=False)


def get_url(metadata: dict):
    df = pd.read_csv(config.url_csv_path)
    # Since `file_path` is the absolute path, we only want the part beginning with "dku_website"
    df["file_path_forweb"] = df["file_path"].str.extract(r"(dku_website/.*)")

    try:
        try:
            path = metadata["file_path"]
        except Exception:
            path = metadata["file_directory"] + "/" + metadata["filename"]

        if "dku_website" in path:
            match = re.search(r"dku_website/.*", path)
            if match:
                result = match.group(0)
                matching_row = df[df["file_path_forweb"] == result]
                if not matching_row.empty:
                    return matching_row.iloc[0]["url"]
        else:
            matching_row = df[df["file_path"] == path]
            if not matching_row.empty:
                return matching_row.iloc[0]["url"]
        return "no url"
    except Exception as e:
        return f"no url, error: {str(e)}"


def simplify_nodes(results) -> list[NodeWithScore]:
    return [
        NodeWithScore(
            node=TextNode(
                id_=doc.id,
                text=doc.text,
                metadata={
                    "filename": os.path.basename(doc.file_path),
                    "url": get_url({"file_path": doc.file_path}),
                    "page_number": doc.page_number,
                },
            ),
            score=float(doc.score),
        )
        for doc in results.docs
    ]


def chroma_result_to_nodes(result: QueryResult) -> list[NodeWithScore]:
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
                    "filename": metadatas[i].get("file_name", "Not given."),
                    "url": get_url(metadatas[i]),
                    "page_number": metadatas[i].get("page_number", "Not given."),
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


# Adapted from: https://github.com/Arize-ai/openinference/blob/a0e6f30c84011c5c743625bb69b66ba055ac17bd/python/instrumentation/openinference-instrumentation-langchain/src/openinference/instrumentation/langchain/_tracer.py#L293-L308 # noqa: E501
def _flatten(
    key_values: Mapping[str, Any],
) -> Iterator[tuple[str, AttributeValue]]:

    for key, value in key_values.items():
        if value is None:
            continue
        if isinstance(value, Mapping):
            for sub_key, sub_value in _flatten(value):
                yield f"{key}.{sub_key}", sub_value
        elif isinstance(value, list) and any(
            isinstance(item, Mapping) for item in value
        ):
            for index, sub_mapping in enumerate(value):
                for sub_key, sub_value in _flatten(sub_mapping):
                    yield f"{key}.{index}.{sub_key}", sub_value
        else:
            if isinstance(value, Enum):
                value = value.value
            yield key, value


def nodes_to_openinference(nodes: list[NodeWithScore]) -> dict[str, Any]:
    return dict(
        _flatten(
            {
                SpanAttributes.RETRIEVAL_DOCUMENTS: [
                    {
                        DocumentAttributes.DOCUMENT_ID: node.node_id,
                        DocumentAttributes.DOCUMENT_SCORE: float(node.score),
                        DocumentAttributes.DOCUMENT_CONTENT: node.text,
                        **(
                            {
                                DocumentAttributes.DOCUMENT_METADATA: safe_json_dumps(
                                    metadata
                                )
                            }
                            if (metadata := node.node.metadata)
                            else {}
                        ),
                    }
                    for node in nodes
                ]
            }
        )
    )
