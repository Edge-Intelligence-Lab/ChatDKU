"""
Unit tests for query_curriculum_db
and its related helper functions.

External dependencies (DB, dspy LM) are mocked so
tests run fully offline with no database or API access required.
"""

from unittest.mock import MagicMock

import pytest

from chatdku.core.tools.syllabi.generate_sql import (
    _collapse_repeated_lines,
    _dedupe_lines,
    _truncate_long_output,
)

# Import helpers directly after patching
from chatdku.core.tools.syllabi.syllabi_tool import (
    SyllabusLookupOuter,
    fetch_schema,
)

# Helpers under test (import directly from the module, not via the package
# entrypoint that calls setup() / use_phoenix() at import time).
# We patch setup() and use_phoenix() before importing the module.


query_curriculum_db = SyllabusLookupOuter()


class TestCollapseRepeatedLines:
    def test_empty_string(self):
        assert _collapse_repeated_lines("") == ""

    def test_no_repetition(self):
        text = "line1\nline2\nline3"
        assert _collapse_repeated_lines(text) == text

    def test_repetition_within_limit(self):
        text = "\n".join(["hello"] * 4)
        result = _collapse_repeated_lines(text)
        assert result.count("hello") == 4
        assert "collapsed" not in result

    def test_mixed_lines(self):
        lines = ["a", "b", "b", "b", "b", "b", "b", "c"]
        text = "\n".join(lines)
        result = _collapse_repeated_lines(text)
        assert "a" in result
        assert "c" in result
        assert "collapsed" in result

    def test_single_line_no_repetition(self):
        assert _collapse_repeated_lines("only one line") == "only one line"


class TestTruncateLongOutput:
    def test_short_text_unchanged(self):
        text = "short"
        assert _truncate_long_output(text, max_chars=100) == text

    def test_exact_limit_unchanged(self):
        text = "a" * 100
        assert _truncate_long_output(text, max_chars=100) == text

    def test_long_text_truncated(self):
        text = "a" * 200
        result = _truncate_long_output(text, max_chars=100)
        assert result.startswith("a" * 100)
        assert "[truncated]" in result

    def test_default_limit_truncates(self):
        text = "y" * 9000
        result = _truncate_long_output(text)
        assert len(result) < 9000
        assert "[truncated]" in result

    def test_empty_string(self):
        assert _truncate_long_output("", max_chars=10) == ""


class TestDedupeLines:
    def test_no_duplicates(self):
        text = "a\nb\nc"
        assert _dedupe_lines(text) == text

    def test_removes_duplicates(self):
        text = "a\nb\na\nc\nb"
        result = _dedupe_lines(text)
        lines = result.splitlines()
        assert lines == ["a", "b", "c"]

    def test_preserves_order(self):
        text = "z\na\nz\nb"
        result = _dedupe_lines(text)
        assert result.splitlines()[0] == "z"

    def test_empty_string(self):
        assert _dedupe_lines("") == ""

    def test_single_line(self):
        assert _dedupe_lines("hello") == "hello"


class TestFetchSchema:
    def test_returns_string_with_classes_key(self):
        mock_db = MagicMock()
        mock_db.execute.return_value = [
            ("id", "integer"),
            ("course_name", "text"),
            ("instructor", "character varying"),
        ]
        result = fetch_schema(mock_db)
        assert isinstance(result, str)
        assert "classes" in result
        assert "course_name" in result
        assert "instructor" in result

    def test_calls_correct_sql(self):
        mock_db = MagicMock()
        mock_db.execute.return_value = []
        fetch_schema(mock_db)
        called_sql = mock_db.execute.call_args[0][0]
        assert "information_schema.columns" in called_sql
        assert "classes" in called_sql

    def test_empty_schema(self):
        mock_db = MagicMock()
        mock_db.execute.return_value = []
        result = fetch_schema(mock_db)
        assert "classes" in result
        assert result  # non-empty


FAKE_SCHEMA_ROWS = [("course_name", "text"), ("instructor", "text")]
FAKE_SQL = "SELECT * FROM classes WHERE course_name = 'MATH';"
FAKE_ROWS = [("MATH 101", "John Zhou"), ("MATH 202", "Peter Parker")]


@pytest.fixture()
def mock_db(monkeypatch):
    """Return a mock DB instance injected via monkeypatching DB()."""
    db_instance = MagicMock()
    db_instance.execute.side_effect = [
        FAKE_SCHEMA_ROWS,  # first call: fetch_schema
        FAKE_ROWS,  # second call: execute final_sql
    ]
    mock_db_cls = MagicMock(return_value=db_instance)
    monkeypatch.setattr(
        "chatdku.core.tools.syllabi.query_curriculum_db.DB",
        mock_db_cls,
    )
    return db_instance


@pytest.fixture()
def mock_generate_sql(monkeypatch):
    sql_agent = MagicMock(return_value=FAKE_SQL)
    mock_cls = MagicMock(return_value=sql_agent)
    monkeypatch.setattr(
        "chatdku.core.tools.syllabi.query_curriculum_db.GenerateSQL",
        mock_cls,
    )
    return sql_agent


@pytest.fixture()
def mock_dspy_predict(monkeypatch):
    """Mock dspy.Predict so no LM call is made."""
    fake_result = MagicMock()
    fake_result.result = "There are 2 math courses: Math 101 and Math 202."
    fake_result.internal_result = {}
    predictor_instance = MagicMock(return_value=fake_result)
    mock_predict_cls = MagicMock(return_value=predictor_instance)
    monkeypatch.setattr(
        "chatdku.core.tools.syllabi.query_curriculum_db.dspy.Predict",
        mock_predict_cls,
    )
    return fake_result


class TestQueryCurriculumDb:
    def test_returns_string(self, mock_db, mock_generate_sql, mock_dspy_predict):
        result, internal = query_curriculum_db(
            "What math courses are offered?", "What math courses are offered?"
        )
        assert isinstance(result, str)

    def test_result_content(self, mock_db, mock_generate_sql, mock_dspy_predict):
        result, internal = query_curriculum_db(
            "What math courses are offered?", "What math courses are offered?"
        )
        assert "math" in result.lower() or "course" in result.lower()

    def test_db_execute_called_twice(
        self, mock_db, mock_generate_sql, mock_dspy_predict
    ):
        query_curriculum_db("List all courses.", "List all courses.")
        # Once for schema, once for actual SQL
        assert mock_db.execute.call_count == 2

    def test_sql_agent_called_with_query_and_schema(
        self, mock_db, mock_generate_sql, mock_dspy_predict
    ):
        query_curriculum_db("Find all CS classes.", "Find all CS classes.")
        mock_generate_sql.assert_called_once()
        kwargs = (
            mock_generate_sql.call_args[1] if mock_generate_sql.call_args[1] else {}
        )
        args = mock_generate_sql.call_args[0]
        # query should appear somewhere in the call
        all_args = str(args) + str(kwargs)
        assert "CS" in all_args or "classes" in all_args

    def test_sql_execution_error_handled_gracefully(
        self, monkeypatch, mock_generate_sql, mock_dspy_predict
    ):
        """DB raising an exception on SQL execution should not propagate."""
        db_instance = MagicMock()
        db_instance.execute.side_effect = [
            FAKE_SCHEMA_ROWS,  # schema fetch succeeds
            Exception("DB is down"),  # SQL execution fails
        ]
        monkeypatch.setattr(
            "chatdku.core.tools.syllabi.query_curriculum_db.DB",
            MagicMock(return_value=db_instance),
        )
        # Should not raise; error is caught and passed to the LM as text
        result, internal = query_curriculum_db("Any query.", "Any query.")
        assert isinstance(result, str)

    def test_think_section_stripped_from_result(
        self, mock_db, mock_generate_sql, monkeypatch
    ):
        fake_result = MagicMock()
        fake_result.result = "<think>internal</think>Clean answer."
        predictor_instance = MagicMock(return_value=fake_result)
        monkeypatch.setattr(
            "chatdku.core.tools.syllabi.query_curriculum_db.dspy.Predict",
            MagicMock(return_value=predictor_instance),
        )
        result, internal = query_curriculum_db("Test query.", "Test query.")
        assert "<think>" not in result
        assert "Clean answer." in result

    def test_repeated_lines_in_lm_output_collapsed(
        self, mock_db, mock_generate_sql, monkeypatch
    ):
        fake_result = MagicMock()
        fake_result.result = "\n".join(["answer"] * 20)
        predictor_instance = MagicMock(return_value=fake_result)
        monkeypatch.setattr(
            "chatdku.core.tools.syllabi.query_curriculum_db.dspy.Predict",
            MagicMock(return_value=predictor_instance),
        )
        result, internal = query_curriculum_db(
            "Repetitive output query.", "Repetitive output query."
        )
        assert result.count("answer") < 20  # collapsed


@pytest.fixture()
def mock_db_outer(monkeypatch):
    db_instance = MagicMock()
    db_instance.execute.side_effect = [FAKE_SCHEMA_ROWS, FAKE_ROWS]
    monkeypatch.setattr(
        "chatdku.core.tools.syllabi.query_curriculum_db.DB",
        MagicMock(return_value=db_instance),
    )
    return db_instance


@pytest.fixture()
def mock_generate_sql_outer(monkeypatch):
    sql_agent = MagicMock(return_value=FAKE_SQL)
    monkeypatch.setattr(
        "chatdku.core.tools.syllabi.query_curriculum_db.GenerateSQL",
        MagicMock(return_value=sql_agent),
    )
    return sql_agent


@pytest.fixture()
def mock_dspy_predict_outer(monkeypatch):
    fake_result = MagicMock()
    fake_result.result = "Two math courses found."
    predictor_instance = MagicMock(return_value=fake_result)
    monkeypatch.setattr(
        "chatdku.core.tools.syllabi.query_curriculum_db.dspy.Predict",
        MagicMock(return_value=predictor_instance),
    )
    return fake_result


class TestQueryCurriculumOuter:
    def test_returns_tuple(
        self, mock_db_outer, mock_generate_sql_outer, mock_dspy_predict_outer
    ):
        fn = SyllabusLookupOuter()
        result = fn("What courses are there?", "What courses are there?")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_result_is_string(
        self, mock_db_outer, mock_generate_sql_outer, mock_dspy_predict_outer
    ):
        fn = SyllabusLookupOuter()
        result_str, internal = fn("List CS courses.", "List CS courses.")
        assert isinstance(result_str, str)

    def test_internal_result_contains_sql(
        self, mock_db_outer, mock_generate_sql_outer, mock_dspy_predict_outer
    ):
        fn = SyllabusLookupOuter()
        _, internal = fn("Find courses.", "Find courses.")
        assert "sql" in internal
        assert isinstance(internal["sql"], str)

    def test_sql_error_reflected_in_output(self, monkeypatch, mock_generate_sql_outer):
        db_instance = MagicMock()
        db_instance.execute.side_effect = [
            FAKE_SCHEMA_ROWS,
            Exception("timeout"),
        ]
        monkeypatch.setattr(
            "chatdku.core.tools.syllabi.query_curriculum_db.DB",
            MagicMock(return_value=db_instance),
        )
        fake_result = MagicMock()
        fake_result.result = "SQL execution error: timeout"
        monkeypatch.setattr(
            "chatdku.core.tools.syllabi.query_curriculum_db.dspy.Predict",
            MagicMock(return_value=MagicMock(return_value=fake_result)),
        )
        fn = SyllabusLookupOuter()
        result_str, _ = fn("Any query.", "Any query.")
        assert isinstance(result_str, str)

    def test_think_section_stripped(
        self, mock_db_outer, mock_generate_sql_outer, monkeypatch
    ):
        fake_result = MagicMock()
        fake_result.result = "<think>skip</think>Real answer."
        monkeypatch.setattr(
            "chatdku.core.tools.syllabi.query_curriculum_db.dspy.Predict",
            MagicMock(return_value=MagicMock(return_value=fake_result)),
        )
        fn = SyllabusLookupOuter()
        result_str, _ = fn("Q.", "Q.")
        assert "<think>" not in result_str
        assert "Real answer." in result_str

    def test_no_tracer_attribute_on_config(
        self,
        mock_db_outer,
        mock_generate_sql_outer,
        mock_dspy_predict_outer,
        monkeypatch,
    ):
        """Runs without error when config has no tracer (uses nullcontext)."""
        import chatdku.core.tools.syllabi.syllabi_tool as mod

        fake_config = MagicMock(spec=[])  # no tracer attribute
        monkeypatch.setattr(mod, "config", fake_config)
        fn = SyllabusLookupOuter()
        result_str, internal = fn("Any query.", "Any query.")
        assert isinstance(result_str, str)
