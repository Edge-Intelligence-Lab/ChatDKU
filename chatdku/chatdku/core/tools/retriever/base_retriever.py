"By: Temuulen. Ask him if you don't understand"

from contextlib import nullcontext
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
from opentelemetry.trace import Status, StatusCode
from opentelemetry.util.types import AttributeValue

from chatdku.config import config


@dataclass
class NodeWithScore:
    node_id: str
    text: str
    metadata: dict
    score: float


class BaseDocRetriever:
    def __init__(
        self,
        internal_memory: dict,
        retriever_top_k: int = 25,
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list | None = None,
    ):
        self.exclude = list(internal_memory.get("ids", set()))
        self.retriever_top_k = retriever_top_k
        self.user_id = user_id
        self.search_mode = search_mode
        self.files = files

    def query(self, query: str) -> list[NodeWithScore]:
        """
        Retrieve texts from the database.

        This is where you should implement your search logic.
        """
        raise NotImplementedError

    def query_with_tell(self, query: str) -> list:
        """
        Retrieve texts from the database with telemetry enabled.
        Uses the `self.query` method to retrieve the results.

        Uses opentelemetry to track the query and the response.
        """
        with (
            config.tracer.start_as_current_span(self.__class__.__name__)
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            exclude = self.exclude
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        dict(
                            query=query,
                            exclude=exclude,
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
