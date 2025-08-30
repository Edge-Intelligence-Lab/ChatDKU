import dspy
import re


def sanitize_sql(sql):
    sql = sql.strip().lower()
    altering_keywords = [
        "insert",
        "update",
        "delete",
        "drop",
        "truncate",
        "alter",
        "create",
        "replace",
        "grant",
        "revoke",
        "comment",
        "rename",
        "set",
        "copy",
        "vacuum",
        "analyze",
    ]

    for keyword in altering_keywords:
        # match full words only to avoid substring match (e.g., 'create' in 'recreate')
        if f" {keyword} " in f" {sql} ":
            return "SELECT 'UNAUTHORIZED';"

    return sql


def extract_sql_regex(text):
    # Case-insensitive search for "sql: " followed by anything until ";"
    pattern = r"sql:\s*(.*?);"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if match:
        return match.group(1).strip() + ";"
    else:
        return text


class TableSelectionSignature(dspy.Signature):
    """
    Select relevant tables for a query, with reasoning.
    Be sure to differentiate courses and classes as one course can have many classes.
    The column course_code may or may not have a space between the course id name and level, meaning ‘MATH 101’ could also be ‘MATH101’.
    Remeber to be case-insensitive for every SQL query.
    Don't take the request too literally, try to give as much info for the user as possible.
    """

    natural_language_query = dspy.InputField(desc="User's natural language question")
    db_schema = dspy.InputField(desc="Database schema in a readable format")
    selected_tables = dspy.OutputField(desc="List of table names required")
    reasoning = dspy.OutputField(desc="Why these tables are selected")


class ColumnSelectionSignature(dspy.Signature):
    """Select relevant columns given tables and the query."""

    selected_tables = dspy.InputField(desc="Tables chosen")
    selection_reason = dspy.InputField(
        desc="Why these tables were chosen to build the SQL query."
    )
    natural_language_query = dspy.InputField(desc="User's question")
    db_schema = dspy.InputField(desc="Database schema for selected tables")
    selected_columns = dspy.OutputField(desc="List of column names required")


class Text2SQLSignature(dspy.Signature):
    """
    Generate pure SQL given the user question, tables, and columns without any ```.
    Use fuzzy search using ILIKE and % symbols if querying for names, as they may be inconsistent.
    Queries should account for text fields such as course_code that may or may not have spaces in the middle.
    """

    natural_language_query = dspy.InputField(desc="User's natural language question")
    sql_context = dspy.InputField(desc="Short schema+reasoning context")
    sql = dspy.OutputField(desc="Pure, valid PostgreSQL query ending with semicolon")


class GenerateSQL(dspy.Module):
    def __init__(self):
        super().__init__()
        self.table_selector = dspy.Predict(TableSelectionSignature)
        self.column_selector = dspy.Predict(ColumnSelectionSignature)
        self.sql_generator = dspy.Predict(Text2SQLSignature)

    def forward(self, query, db_schema: str):
        # print("Selecting table...")
        table_result = self.table_selector(
            natural_language_query=query, db_schema=db_schema
        )
        # print("Selecting columns...")
        column_result = self.column_selector(
            selected_tables=table_result.selected_tables,
            selection_reason=table_result.reasoning,
            natural_language_query=query,
            db_schema=db_schema,
        )
        # print("Columns selected. Building context.")
        context = f"Tables: {table_result.selected_tables}\nColumns: {
            column_result.selected_columns
        }\nReasoning: {table_result.reasoning}"
        # print("Context taken. Building SQL query. ")
        sql_result = self.sql_generator(
            natural_language_query=query, sql_context=context
        )
        # print(sql_result.sql)
        return sanitize_sql(extract_sql_regex(sql_result.sql))
