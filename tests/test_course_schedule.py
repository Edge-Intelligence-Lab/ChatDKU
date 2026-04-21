"""Comprehensive tests for chatdku.core.tools.course_schedule."""

import json

import pandas as pd
import pytest
from opentelemetry.trace import StatusCode

from chatdku.core.tools.course_schedule import (
    CourseScheduleLookupOuter,
    _lookup,
    _parse_course,
)


# ---------------------------------------------------------------------------
# _parse_course (pure function — no mocks needed)
# ---------------------------------------------------------------------------


class TestParseCourse:
    def test_with_space(self):
        assert _parse_course("COMPSCI 101") == ("COMPSCI", "101")

    def test_no_separator(self):
        assert _parse_course("COMPSCI101") == ("COMPSCI", "101")

    def test_with_hyphen(self):
        assert _parse_course("COMPSCI-101") == ("COMPSCI", "101")

    def test_alpha_suffix(self):
        assert _parse_course("Chinese 101A") == ("CHINESE", "101A")

    def test_strips_whitespace(self):
        assert _parse_course("  COMPSCI 101  ") == ("COMPSCI", "101")

    def test_lowercase_normalised_to_upper(self):
        assert _parse_course("math 201") == ("MATH", "201")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _parse_course("")

    def test_only_symbols_raises(self):
        with pytest.raises(ValueError):
            _parse_course("!!!")

    def test_only_numbers_raises(self):
        with pytest.raises(ValueError):
            _parse_course("12345")


# ---------------------------------------------------------------------------
# _lookup (needs a DataFrame, no external mocks)
# ---------------------------------------------------------------------------


@pytest.fixture()
def schedule_df():
    return pd.DataFrame(
        {
            "Subject": ["COMPSCI", "COMPSCI", "MATH", "BIOL"],
            "Catalog": ["101", "201", "201", "305"],
            "Section": ["01", "02", "01", "01"],
            "Instructor": ["Alice", "Bob", "Carol", "Dave"],
        }
    )


class TestLookup:
    def test_finds_matching_rows(self, schedule_df):
        rows = _lookup("COMPSCI 101", schedule_df)
        assert len(rows) == 1
        assert rows[0]["Subject"] == "COMPSCI"
        assert rows[0]["Catalog"] == "101"

    def test_returns_empty_for_nonexistent(self, schedule_df):
        assert _lookup("ASTROLOGY 1239", schedule_df) == []

    def test_case_insensitive(self, schedule_df):
        rows = _lookup("compsci 201", schedule_df)
        assert len(rows) == 1

    def test_multiple_sections(self, schedule_df):
        # Add a second section for COMPSCI 101
        extra = pd.DataFrame(
            {
                "Subject": ["COMPSCI"],
                "Catalog": ["101"],
                "Section": ["02"],
                "Instructor": ["Eve"],
            }
        )
        df = pd.concat([schedule_df, extra], ignore_index=True)
        rows = _lookup("COMPSCI 101", df)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# CourseScheduleLookupOuter (needs mock_span_ctx + CSV fixture)
# ---------------------------------------------------------------------------


class TestCourseScheduleLookupOuter:
    def test_returns_callable(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        assert callable(fn)

    def test_single_course_found(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        result = json.loads(fn(["COMPSCI 101"]))
        assert "COMPSCI 101" in result
        assert isinstance(result["COMPSCI 101"], list)
        assert result["COMPSCI 101"][0]["Instructor"] == "Alice Smith"

    def test_multiple_courses(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        result = json.loads(fn(["COMPSCI 101", "MATH 201"]))
        assert "COMPSCI 101" in result
        assert "MATH 201" in result

    def test_course_not_found_message(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        result = json.loads(fn(["FAKE 999"]))
        assert "No schedule found" in result["FAKE 999"]

    def test_mixed_found_and_not_found(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        result = json.loads(fn(["COMPSCI 101", "FAKE 999"]))
        assert isinstance(result["COMPSCI 101"], list)
        assert "No schedule found" in result["FAKE 999"]

    def test_file_not_found_raises(self, mock_span_ctx):
        fn = CourseScheduleLookupOuter("/nonexistent/path.csv")
        with pytest.raises(FileNotFoundError):
            fn(["COMPSCI 101"])

    def test_span_status_ok_on_success(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        fn(["COMPSCI 101"])
        calls = mock_span_ctx.set_status.call_args_list
        assert any(c.args[0].status_code == StatusCode.OK for c in calls if c.args)

    def test_span_attributes_set(self, mock_span_ctx, sample_classdata_csv):
        fn = CourseScheduleLookupOuter(sample_classdata_csv)
        fn(["COMPSCI 101"])
        assert mock_span_ctx.set_attributes.called
