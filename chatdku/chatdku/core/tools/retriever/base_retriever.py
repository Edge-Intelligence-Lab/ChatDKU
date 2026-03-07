"By: Temuulen. Ask him if you don't understand"

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Mapping

from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    DocumentAttributes,
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode, set_span_in_context
from opentelemetry.util.types import AttributeValue

from chatdku.core.utils import span_ctx_start


@dataclass
class NodeWithScore:
    node_id: str
    text: str
    metadata: dict
    score: float


class BaseDocRetriever:
    def __init__(
        self,
        retriever_top_k: int = 25,
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list = [],
    ):
        self.retriever_top_k = retriever_top_k
        self.user_id = user_id
        self.search_mode = search_mode
        self.files = files

    def query(self, query) -> list[NodeWithScore]:
        """
        Retrieve texts from the database.

        This is where you should implement your search logic.
        """
        raise NotImplementedError

    def query_with_tell(self, query, parent_span=None) -> list:
        """
        Retrieve texts from the database with telemetry enabled.
        Uses the `self.query` method to retrieve the results.

        Uses opentelemetry to track the query and the response.
        """
        context = None
        if parent_span is not None:
            context = set_span_in_context(parent_span)
        with span_ctx_start(
            self.__class__.__name__, OpenInferenceSpanKindValues.RETRIEVER, context
        ) as span:
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        dict(
                            query=query,
                            user_id=self.user_id,
                            search_mode=self.search_mode,
                            files=self.files,
                        )
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            retrieved_nodes = []

            try:
                retrieved_nodes = self.query(query)
                span.set_attributes(nodes_to_OTLP(retrieved_nodes))
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                            dict(result=retrieved_nodes)
                        ),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
                span.set_status(Status(StatusCode.OK))
                return retrieved_nodes
            except Exception as e:
                span.set_attributes(
                    {
                        SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                            dict(result=str(e))
                        ),
                        SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )
                span.set_status(Status(StatusCode.ERROR))
            return retrieved_nodes


def nodes_to_OTLP(nodes: list[NodeWithScore]) -> dict[str, Any]:
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
                            if (metadata := node.metadata)
                            else {}
                        ),
                    }
                    for node in nodes
                ]
            }
        )
    )


def _flatten(
    key_values: Mapping[str, Any],
) -> Iterator[tuple[str, AttributeValue]]:
    """
    Adapted from:
    https://github.com/Arize-ai/openinference/blob/a0e6f30c84011c5c743625bb69b66ba055ac17bd/python/instrumentation/openinference-instrumentation-langchain/src/openinference/instrumentation/langchain/_tracer.py#L293-L308
    """  # noqa: E501

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
