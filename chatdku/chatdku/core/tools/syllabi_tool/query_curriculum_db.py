from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.core.tools.retriever.base_retriever import NodeWithScore, nodes_to_OTLP
from chatdku.core.tools.syllabi_tool.generate_sql import GenerateSQL
from chatdku.core.utils import span_ctx_start
from chatdku.setup import DB


def _collapse_repeated_lines(text: str, max_consecutive: int = 4) -> str:
    """Collapse long runs of the same consecutive line to avoid runaway repetition.

    Example: if a line repeats 100 times, keep one and add a collapse note.
    """
    if not text:
        return text
    lines = text.splitlines()
    out_lines = []
    prev = None
    count = 0
    for line in lines:
        if line == prev:
            count += 1
        else:
            if prev is not None:
                if count > max_consecutive:
                    out_lines.append(prev)
                    out_lines.append(f"...({count+1} repeated lines collapsed)...")
                else:
                    out_lines.extend([prev] * (count + 1))
            prev = line
            count = 0

    # flush
    if prev is not None:
        if count > max_consecutive:
            out_lines.append(prev)
            out_lines.append(f"...({count+1} repeated lines collapsed)...")
        else:
            out_lines.extend([prev] * (count + 1))

    return "\n".join(out_lines)


def _truncate_long_output(text: str, max_chars: int = 8000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _dedupe_lines(text: str) -> str:
    """Remove duplicated lines while preserving order."""
    seen = set()
    out = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)


def fetch_schema(db: DB) -> str:
    """Fetch simple schema description from the 'classes' table."""
    sql = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'classes';
    """
    rows = db.execute(sql)
    schema = {"classes": {col: dtype for col, dtype in rows}}
    return str(schema)


def QueryCurriculumOuter():
    def QueryCurriculum(query: str, current_user_message: str) -> tuple[str, dict]:
        """
        Takes a natural language query about courses and classes offered at Duke Kunshan University -> generates intermediate SQL query passed into Postgres -> Result formatted in natural language.

        Args:
            query: String (The information you want to retrieve by using this tool.)
            current_user_message: String (verbatim to user's initial query)
        Returns:
            String
        """
        db = DB()

        with span_ctx_start(
            "Query Curriculum DB", OpenInferenceSpanKindValues.RETRIEVER
        ) as span:
            sql_agent = GenerateSQL()
            db_schema = fetch_schema(db=db)
            final_sql = sql_agent(
                query=query,
                current_user_message=current_user_message,
                db_schema=db_schema,
            ).sql
            # sanitize generated SQL to avoid runaway repetition or duplication
            final_sql = _collapse_repeated_lines(final_sql)
            final_sql = _dedupe_lines(final_sql)
            final_sql = _truncate_long_output(final_sql, max_chars=12000)

            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        dict(query=query, sql=final_sql)
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            try:
                nodes = []
                rows = db.execute(final_sql)
                tool_out = str(rows)
                for i, row in enumerate(rows):
                    nodes.append(
                        NodeWithScore(
                            node_id=str(i),
                            text=str(row),
                            metadata={},
                            score=1.0,
                        )
                    )
                span.set_attributes(nodes_to_OTLP(nodes))
            except Exception as e:
                rows = None
                tool_out = f"SQL execution error: {e}"
                span.set_status(Status(StatusCode.ERROR), str(e))

            internal_result = {"sql": final_sql}

        return tool_out, internal_result

    return QueryCurriculum
