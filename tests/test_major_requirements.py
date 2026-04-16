"""Tests for chatdku.core.tools.major_requirements."""

import pytest
from opentelemetry.trace import StatusCode

from chatdku.core.tools.major_requirements import (
    MajorRequirementsLookupOuter,
    _best_match,
    _jaccard,
    _list_stems,
    _tokenize,
)


# ---------------------------------------------------------------------------
# _tokenize (pure)
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_lowercases(self):
        assert _tokenize("Data Science") == {"data", "science"}

    def test_strips_separators(self):
        result = _tokenize("data-science/track")
        assert "data" in result
        assert "science" in result
        assert "track" in result

    def test_removes_punctuation(self):
        result = _tokenize("hello! world?")
        assert result == {"hello", "world"}

    def test_empty_string(self):
        assert _tokenize("") == set()


# ---------------------------------------------------------------------------
# _jaccard (pure)
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        # intersection={b,c}, union={a,b,c,d} → 2/4 = 0.5
        assert _jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 0.0


# ---------------------------------------------------------------------------
# _best_match (pure)
# ---------------------------------------------------------------------------


class TestBestMatch:
    STEMS = [
        "data-science",
        "computation-and-design-computer-science",
        "behavioral-science-psychology",
        "requirements-for-all-majors",
    ]

    def test_exact_match(self):
        assert _best_match("data science", self.STEMS) == "data-science"

    def test_partial_match(self):
        result = _best_match("computer science", self.STEMS)
        assert result == "computation-and-design-computer-science"

    def test_no_match_returns_none(self):
        assert _best_match("astrology", self.STEMS) is None

    def test_empty_query_returns_none(self):
        assert _best_match("", self.STEMS) is None

    def test_requirements_for_all(self):
        result = _best_match("requirements for all majors", self.STEMS)
        assert result == "requirements-for-all-majors"


# ---------------------------------------------------------------------------
# _list_stems
# ---------------------------------------------------------------------------


class TestListStems:
    def test_returns_sorted_stems(self, tmp_path):
        (tmp_path / "b-major.md").write_text("B")
        (tmp_path / "a-major.md").write_text("A")
        stems = _list_stems(tmp_path)
        assert stems == ["a-major", "b-major"]

    def test_ignores_non_md_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("text")
        (tmp_path / "data.md").write_text("data")
        stems = _list_stems(tmp_path)
        assert stems == ["data"]

    def test_empty_dir(self, tmp_path):
        assert _list_stems(tmp_path) == []


# ---------------------------------------------------------------------------
# MajorRequirementsLookupOuter (needs mock_span_ctx + tmp dir with .md files)
# ---------------------------------------------------------------------------


@pytest.fixture()
def requirements_dir(tmp_path):
    """Create a temporary requirements directory with sample .md files."""
    (tmp_path / "data-science.md").write_text(
        "# Data Science\n\n- COMPSCI 101\n- STATS 202\n"
    )
    (tmp_path / "computation-and-design-computer-science.md").write_text(
        "# Computation and Design / Computer Science\n\n- COMPSCI 201\n"
    )
    (tmp_path / "requirements-for-all-majors.md").write_text(
        "# General Requirements\n\n- WRIT 101\n- MATH 101\n"
    )
    return str(tmp_path)


class TestMajorRequirementsLookupOuter:
    def test_returns_callable(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        assert callable(fn)

    def test_list_returns_all_majors(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        result = fn("list")
        assert "data-science" in result
        assert "computation-and-design-computer-science" in result
        assert "requirements-for-all-majors" in result

    def test_lookup_returns_file_content(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        result = fn("data science")
        assert "COMPSCI 101" in result
        assert "STATS 202" in result

    def test_lookup_prepends_requirements_header(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        result = fn("data science")
        assert result.startswith("# Requirements:")

    def test_no_match_returns_message(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        result = fn("astrology")
        assert "No matching major" in result

    def test_nonexistent_directory_raises(self, mock_span_ctx):
        fn = MajorRequirementsLookupOuter("/nonexistent/path")
        with pytest.raises(FileNotFoundError):
            fn("data science")

    def test_empty_directory_raises(self, mock_span_ctx, tmp_path):
        fn = MajorRequirementsLookupOuter(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            fn("data science")

    def test_span_status_ok_on_success(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        fn("data science")
        calls = mock_span_ctx.set_status.call_args_list
        assert any(c.args[0].status_code == StatusCode.OK for c in calls if c.args)

    def test_span_attributes_set(self, mock_span_ctx, requirements_dir):
        fn = MajorRequirementsLookupOuter(requirements_dir)
        fn("data science")
        assert mock_span_ctx.set_attributes.called
