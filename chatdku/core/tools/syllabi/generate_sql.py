import re
from typing import Literal

import dspy


class Text2SQLSignature(dspy.Signature):
    """
    Generates pure SQL (PostgreSQL dialect) given the user question, tables, and columns without any backticks,
    to be run on a database of the classes offered at Duke Kunshan University (DKU).

    Uses fuzzy search using regex, ILIKE, and % symbols when querying for a course or a person's name, as they may be inconsistent.
    Text fields course_code may or may not a space in the middle, so must be accounted for by adding the regex % between the name and the number.
    Do not write overly broad regex such as %cs%, as this can catch unrelated entries.
    Do not include the words professor or instructor when querying.
    Do not include any title, suffix, or honorifics when querying.
    Always select at least 4 relevant columns when composing SQL queries.
    If you don't know the values of the fields, you can use `SELECT DISTINCT` to get a list of all possible values.

    Decide whether to continue or finish:
       - Choose "continue" if there needs to be more information retrieved
       - Choose "finish" if you have gathered enough information to answer the
         user's question, OR if the remaining gaps cannot be resolved with
         further tool calls.

    Do note that:
        - For computer science subject code, we use the code "COMPSCI" instead of "CS".

    Return 'finish' in the field sql which marks the task as complete. That is, signals that all information for asnwering the current_user_message are now available to be extracted.
    """  # noqa: E501

    natural_language_query = dspy.InputField(desc="Agent's natural language question")
    current_user_message = dspy.InputField(desc="User's initial prompt")
    sql_context = dspy.InputField(desc="PostgreSQL table schema.")
    trajectory: dict = dspy.InputField(desc="The results of your previous query.")
    action: str = dspy.OutputField(type=Literal["continue", "finish"])
    sql = dspy.OutputField(desc="Pure, valid PostgreSQL query ending with semicolon")


class GenerateSQL(dspy.Module):
    def __init__(self):
        super().__init__()
        self.sql_generator = dspy.ChainOfThought(Text2SQLSignature)

    def forward(self, query, current_user_message, db_schema: str, trajectory: dict):
        pred = self.sql_generator(
            natural_language_query=query,
            current_user_message=current_user_message,
            sql_context=db_schema,
            trajectory=trajectory,
        )
        action = pred.action
        sql_result = pred.sql
        if action.lower() == "finish":
            return dspy.Prediction(sql="finish")
        sql_result = sanitize_sql(extract_sql_regex(sql_result))
        # sanitize generated SQL to avoid runaway repetition or duplication
        sql_result = _collapse_repeated_lines(sql_result)
        sql_result = _dedupe_lines(sql_result)
        sql_result = _truncate_long_output(sql_result, max_chars=12000)
        return dspy.Prediction(sql=sql_result, reasoning=pred.reasoning)


def sanitize_sql(sql):
    sql = extract_sql_regex(sql)
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
    # Case-insensitive extraction from "sql: " followed by anything until ";"
    pattern = r"sql:\s*(.*?);"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if match:
        return match.group(1).strip() + ";"
    else:
        return text


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
                    out_lines.append(f"...({count + 1} repeated lines collapsed)...")
                else:
                    out_lines.extend([prev] * (count + 1))
            prev = line
            count = 0

    # flush
    if prev is not None:
        if count > max_consecutive:
            out_lines.append(prev)
            out_lines.append(f"...({count + 1} repeated lines collapsed)...")
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
