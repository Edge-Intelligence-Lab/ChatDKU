#!/usr/bin/env python3
"""
SQLAgentOuter: Factory function to create a callable SQLAgent,
similar to VectorRetrieverOuter. Encapsulates DB connection internally
and returns a minimal interface for DSPy tools.
"""

from contextlib import nullcontext
import os
import psycopg2
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import Status, StatusCode, use_span
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.core.tools.course_schedule.sql_agent import SQLAgent
from chatdku.config import config


def SQLAgentOuter(internal_memory: dict):
    """
    Returns a callable that executes SQL queries via SQLAgent.
    Uses `config.psql_uri` internally.
    """

    # Connect using URI
    conn = psycopg2.connect(config.psql_uri)
    sql_agent = SQLAgent(conn)

    def SQLAgentCallable(query: str):
        """Query the official DKU course database.
        Use this tool to answer questions about:
        - which course a professor teaches
        - course offerings by semester (e.g., Spring 2026)
        - instructor–course assignments
        - course session and time
        This tool is the authoritative source for course information."""
        span = None
        if hasattr(config, "tracer"):
            span = config.tracer.start_span("SQL Agent")
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        {"query": query, "internal_memory": internal_memory}
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

        with use_span(span) if span else nullcontext():
            try:
                result = sql_agent.forward(query)
                internal_result = {"raw_rows": result.get("raw_rows", [])}

                if span:
                    span.set_attributes(
                        {
                            SpanAttributes.OUTPUT_VALUE: safe_json_dumps(result),
                            SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                        }
                    )
                    span.set_status(Status(StatusCode.OK))

                return result, internal_result

            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR))
                    span.end()
                return {
                    "sql": None,
                    "answer": f"Sorry, encountered error executing SQL: {str(e)}",
                }, {"raw_rows": []}

    return SQLAgentCallable