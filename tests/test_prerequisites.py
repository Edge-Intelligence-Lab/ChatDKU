"""Tests for chatdku.core.tools.get_prerequisites."""

import pytest
from opentelemetry.trace import StatusCode

from chatdku.core.tools.get_prerequisites import PrerequisiteLookupOuter, get_prereq


# ---------------------------------------------------------------------------
# get_prereq (internal helper)
# ---------------------------------------------------------------------------


class TestGetPrereq:
    def test_returns_prerequisite_description(self, sample_prereq_csv):
        result = get_prereq("COMPSCI 201", sample_prereq_csv)
        assert "(Source: DKUHub)" in result
        assert "COMPSCI" in result

    def test_uses_latest_effective_date(self, sample_prereq_csv):
        """Two rows for COMPSCI 201 — should pick the 09/01/2024 entry."""
        result = get_prereq("COMPSCI 201", sample_prereq_csv)
        assert "COMPSCI 102" in result  # only in the newer row

    def test_returns_not_found_for_unknown_course(self, sample_prereq_csv):
        result = get_prereq("ASTRO 999", sample_prereq_csv)
        assert "No prerequisites found" in result

    def test_empty_description_returns_not_found(self, sample_prereq_csv):
        """BIOL 305 has an empty description in col 13."""
        result = get_prereq("BIOL 305", sample_prereq_csv)
        assert "No prerequisites found" in result

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            get_prereq("COMPSCI 201", "/nonexistent/path.csv")

    def test_handles_extra_spaces_in_course_name(self, sample_prereq_csv):
        result = get_prereq("COMPSCI  201", sample_prereq_csv)
        # Should still parse — splits on underscore after space→underscore replacement
        assert "COMPSCI" in result

    def test_known_course_with_prereqs(self, sample_prereq_csv):
        result = get_prereq("MATH 201", sample_prereq_csv)
        assert "MATH 101" in result
        assert "(Source: DKUHub)" in result


# ---------------------------------------------------------------------------
# PrerequisiteLookupOuter (needs mock_span_ctx + sample CSV)
# ---------------------------------------------------------------------------


class TestPrerequisiteLookupOuter:
    def test_returns_callable(self, mock_span_ctx, sample_prereq_csv):
        fn = PrerequisiteLookupOuter(sample_prereq_csv)
        assert callable(fn)

    def test_single_course_lookup(self, mock_span_ctx, sample_prereq_csv):
        fn = PrerequisiteLookupOuter(sample_prereq_csv)
        result = fn(["MATH 201"])
        assert "MATH 101" in result

    def test_multiple_courses_joined_by_newline(self, mock_span_ctx, sample_prereq_csv):
        fn = PrerequisiteLookupOuter(sample_prereq_csv)
        result = fn(["COMPSCI 201", "MATH 201"])
        assert "\n" in result
        assert "COMPSCI" in result
        assert "MATH" in result

    def test_file_not_found_propagates(self, mock_span_ctx):
        fn = PrerequisiteLookupOuter("/nonexistent/path.csv")
        with pytest.raises(FileNotFoundError):
            fn(["COMPSCI 201"])

    def test_span_status_ok_on_success(self, mock_span_ctx, sample_prereq_csv):
        fn = PrerequisiteLookupOuter(sample_prereq_csv)
        fn(["MATH 201"])
        calls = mock_span_ctx.set_status.call_args_list
        assert any(c.args[0].status_code == StatusCode.OK for c in calls if c.args)

    def test_span_attributes_set(self, mock_span_ctx, sample_prereq_csv):
        fn = PrerequisiteLookupOuter(sample_prereq_csv)
        fn(["MATH 201"])
        assert mock_span_ctx.set_attributes.called
