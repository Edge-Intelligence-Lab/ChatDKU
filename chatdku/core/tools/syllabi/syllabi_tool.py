import dspy
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.core.tools.retriever.base_retriever import NodeWithScore, nodes_to_OTLP
from chatdku.core.tools.syllabi.generate_sql import GenerateSQL
from chatdku.core.utils import span_ctx_start
from chatdku.setup import DB

table_name = "curriculum"


def SyllabusLookupOuter(N=3):
    db = DB()
    sql_agent = GenerateSQL()
    db_schema = fetch_schema(db=db)

    def SyllabusLookup(query: str, current_user_message: str) -> tuple[str, dict]:
        """
        Takes a natural language query about course syllabus -> generates intermediate SQL query
        passed into Postgres which has courses' syllabi -> Result formatted in natural language.

        It can answer what a specific course covers, what kind of assignments
        are given, and a course's grading policy.

        Good tool for syllabus questions.

        Args:
            query: String (The information you want to retrieve by using this tool.)
            current_user_message: String (verbatim to user's initial query)
        Returns:
            String
        """
        internal_result = {}
        trajectory = {}
        tool_out = ""
        for idx in range(N):
            pred = sql_agent(
                query=query,
                current_user_message=current_user_message,
                db_schema=db_schema,
                trajectory=trajectory,
            )
            sql = pred.sql
            if sql == "finish":
                break
            internal_result = {"sql": sql}
            nodes = []

            with span_ctx_start(
                "Query Curriculum DB", OpenInferenceSpanKindValues.RETRIEVER
            ) as span:
                span.set_attributes(
                    {
                        SpanAttributes.INPUT_VALUE: safe_json_dumps(
                            dict(query=query, sql=sql)
                        ),
                        SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                    }
                )

                try:
                    rows = db.execute(sql)
                    # __import__("pprint").pprint(rows)
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
            trajectory[f"reasoning_{idx}"] = pred.reasoning
            trajectory[f"sql_{idx}"] = pred.sql
            trajectory[f"results_{idx}"] = tool_out

        summarizer = dspy.Predict("tool_trajectory, current_user_message -> answer")
        answer = summarizer(
            tool_trajectory=trajectory,
            current_user_message=current_user_message,
        ).answer

        return answer, internal_result

    return SyllabusLookup


def fetch_schema(db: DB) -> str:
    """Fetch simple schema description from the table."""
    sql = f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table_name}';
    """
    distinct_values_sql = {
        "year": f"""
        SELECT DISTINCT year
        FROM {table_name};
        """,
        "semester": f"""
        SELECT DISTINCT semester
        FROM {table_name};
        """,
        "semester_session": f"""
        SELECT DISTINCT semester_session
        FROM {table_name};
        """,
    }
    rows = db.execute(sql)
    schema = {f"{table_name}": {col: dtype for col, dtype in rows}}
    for key, sql in distinct_values_sql.items():
        rows = db.execute(sql)
        schema[key] = {"distinct_values": rows}
    return str(schema)
