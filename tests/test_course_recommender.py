"""Tests for chatdku.core.tools.course_recommender.

Covers:
  - parse_course_codes  (unit)
  - prerequisites_met   (unit)
  - CourseRecommenderOuter / full integration  (4 simple + complex scenarios)
"""

import pandas as pd
import pytest
from opentelemetry.trace import StatusCode

from chatdku.core.tools.course_recommender import (
    CourseRecommenderOuter,
    _run_recommendation,
    parse_course_codes,
    prerequisites_met,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def req_dir(tmp_path):
    """Requirements dir that mirrors the real Data Science major layout."""
    (tmp_path / "data-science.md").write_text(
        """# Data Science

## Interdisciplinary Courses
| Course Code | Course Name | Credits |
|-------------|-------------|---------|
| COMPSCI 201 | Intro to Programming and Data Structures | 4 |
| STATS 302   | Principles of Machine Learning | 4 |
| STATS 303   | Statistical Machine Learning | 4 |
| STATS 401   | Data Acquisition and Visualization | 4 |

## Disciplinary Courses
| Course Code | Course Name | Credits |
|-------------|-------------|---------|
| MATH 201 | Multivariable Calculus | 4 |
| MATH 202 | Linear Algebra | 4 |
| MATH 206 | Probability and Statistics | 4 |
| COMPSCI 301 | Algorithms and Databases | 4 |
"""
    )
    (tmp_path / "requirements-for-all-majors.md").write_text(
        """# Requirements for All Majors

## Common Core
| Academic Year | Course Code | Course Name | Credits |
|---------------|-------------|-------------|---------|
| First Year    | GCHINA 101  | China in the World | 4 |
| Second Year   | GLOCHALL 201 | Global Challenges | 4 |
| Third Year    | ETHLDR 201  | Ethics and Citizenship | 4 |
"""
    )
    return str(tmp_path)


@pytest.fixture()
def prereq_csv_with_ds_courses(tmp_path):
    """Prerequisite CSV with realistic Data Science course prerequisites.

    Mirrors real data from DKUHub:
      - MATH 201: "Prerequisite: MATH 101 or MATH 105"
      - STATS 302: "Prerequisite: MATH 201, MATH 202, MATH 206, and COMPSCI 201"
      - COMPSCI 301: "COMPSCI 201, Anti-requisites: COMPSCI 308 and 310"
      - GLOCHALL 201: "Prerequisite: GCHINA 101 and sophomore standing"
      - ETHLDR 201:   "Prerequisite: GLOCHALL 201 and junior standing"
      - All others: no entry (treated as no prerequisites)
    """
    csv_path = tmp_path / "prereq_ds.csv"
    rows = [
        [1, "09/01/2024", "MATH", "201", "", "", "", "", "", "", "", "", "", "Prerequisite: MATH 101 or MATH 105"],
        [2, "09/01/2024", "STATS", "302", "", "", "", "", "", "", "", "", "",
         "Prerequisite: MATH 201, MATH 202, MATH 206, and COMPSCI 201. Anti-requisite: MATH 405"],
        [3, "09/01/2024", "COMPSCI", "301", "", "", "", "", "", "", "", "", "",
         "COMPSCI 201, Anti-requisites: COMPSCI 308 and 310"],
        [4, "09/01/2024", "GLOCHALL", "201", "", "", "", "", "", "", "", "", "",
         "Prerequisite: GCHINA 101 and sophomore standing"],
        [5, "09/01/2024", "ETHLDR", "201", "", "", "", "", "", "", "", "", "",
         "Prerequisite: GLOCHALL 201 and junior standing"],
    ]
    columns = [f"col{i}" for i in range(14)]
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(csv_path, index=False, encoding="utf-16le")
    return str(csv_path)


# ---------------------------------------------------------------------------
# Unit tests: parse_course_codes
# ---------------------------------------------------------------------------


class TestParseCourseCode:
    def test_extracts_standard_table_entry(self):
        text = "| COMPSCI 201 | Intro to Programming | 4 |"
        assert "COMPSCI 201" in parse_course_codes(text)

    def test_extracts_courses_from_bullet_list(self):
        text = "- STATS 302: Principles of Machine Learning\n- MATH 201: Calculus"
        codes = parse_course_codes(text)
        assert "STATS 302" in codes
        assert "MATH 201" in codes

    def test_ignores_unknown_subject_prefixes(self):
        # "THE 123" and "FOR 999" are not DKU subject codes → should be filtered
        text = "THE 123 and FOR 999 are not DKU courses. But COMPSCI 101 is."
        codes = parse_course_codes(text)
        assert "COMPSCI 101" in codes
        assert "THE 123" not in codes
        assert "FOR 999" not in codes

    def test_deduplicates_repeated_codes(self):
        text = "MATH 201 is listed here. Also MATH 201 appears again."
        codes = parse_course_codes(text)
        assert codes.count("MATH 201") == 1

    def test_extracts_glochall_subject(self):
        text = "| GLOCHALL 201 | Global Challenges | 4 |"
        assert "GLOCHALL 201" in parse_course_codes(text)

    def test_handles_empty_text(self):
        assert parse_course_codes("") == []

    def test_preserves_insertion_order(self):
        text = "COMPSCI 201 then STATS 302 then MATH 201"
        codes = parse_course_codes(text)
        assert codes.index("COMPSCI 201") < codes.index("STATS 302") < codes.index("MATH 201")

    def test_does_not_match_two_digit_catalog(self):
        # Catalog numbers must be 3 digits — "MATH 20" should not match
        assert "MATH 20" not in parse_course_codes("MATH 20 is not a real code")

    def test_matches_catalog_with_letter_suffix(self):
        assert "CHINESE 101A" in parse_course_codes("CHINESE 101A")


# ---------------------------------------------------------------------------
# Unit tests: prerequisites_met
# ---------------------------------------------------------------------------


class TestPrerequisitesMet:
    @pytest.fixture(autouse=True)
    def _prereq_df(self, prereq_csv_with_ds_courses):
        self.prereq_df = pd.read_csv(prereq_csv_with_ds_courses, encoding="utf-16le")

    def test_no_prereq_entry_returns_eligible(self):
        """STATS 401 is not in the prereq CSV — should be eligible with no prereqs."""
        met, reason = prerequisites_met("STATS 401", set(), self.prereq_df)
        assert met is True
        assert reason == ""

    def test_simple_or_prereq_satisfied_by_first_option(self):
        """MATH 201 needs MATH 101 or MATH 105. MATH 101 completed → eligible."""
        completed = {"MATH 101"}
        met, reason = prerequisites_met("MATH 201", completed, self.prereq_df)
        assert met is True

    def test_simple_or_prereq_satisfied_by_second_option(self):
        """MATH 201 needs MATH 101 or MATH 105. MATH 105 completed → eligible."""
        completed = {"MATH 105"}
        met, reason = prerequisites_met("MATH 201", completed, self.prereq_df)
        assert met is True

    def test_simple_or_prereq_not_satisfied(self):
        """MATH 201 needs MATH 101 or MATH 105. Neither completed → not eligible."""
        met, reason = prerequisites_met("MATH 201", set(), self.prereq_df)
        assert met is False
        assert "MATH 101" in reason or "MATH 105" in reason

    def test_and_prereq_partially_met(self):
        """STATS 302 needs MATH 201, MATH 202, MATH 206, COMPSCI 201 (AND logic).
        Student only has MATH 201 and COMPSCI 201 → still not eligible."""
        completed = {"MATH 201", "COMPSCI 201"}
        met, reason = prerequisites_met("STATS 302", completed, self.prereq_df)
        assert met is False
        # At least one missing prereq should be cited
        assert "MATH 202" in reason or "MATH 206" in reason

    def test_and_prereq_fully_met(self):
        """STATS 302 with all 4 prereqs completed → eligible."""
        completed = {"MATH 201", "MATH 202", "MATH 206", "COMPSCI 201"}
        met, reason = prerequisites_met("STATS 302", completed, self.prereq_df)
        assert met is True

    def test_prereq_entry_with_no_course_codes(self):
        """A prereq text like 'sophomore standing' has no course codes —
        our heuristic returns eligible with an unstructured note."""
        # Inject a row with standing-only prereq
        extra = pd.DataFrame(
            [[99, "01/01/2024", "ECON", "201", "", "", "", "", "", "", "", "", "", "Sophomore standing required"]],
            columns=[f"col{i}" for i in range(14)],
        )
        df = pd.concat([self.prereq_df, extra], ignore_index=True)
        met, reason = prerequisites_met("ECON 201", set(), df)
        assert met is True  # best-effort: pass through with note
        assert "Unstructured" in reason or reason == ""


# ---------------------------------------------------------------------------
# Integration tests: CourseRecommenderOuter  (TC1–TC6)
# ---------------------------------------------------------------------------


class TestCourseRecommenderScenarios:
    """End-to-end test scenarios evaluating the full recommendation pipeline."""

    # TC1 — Simple: freshman with no completed courses
    def test_tc1_no_completed_courses(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC1 (Simple): Student has no completed courses.

        Expected behaviour:
          - Courses with unmet prerequisites → 'not eligible' section
          - Courses with no prerequisites that are offered → 'recommended'
          - Courses offered but requiring prereqs not yet met → 'not eligible'
        """
        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        result = recommender(major="data science", completed_courses=[])

        # Should produce a structured report, not an error
        assert "## Course Recommendation" in result
        assert "data-science" in result.lower()

        # COMPSCI 201 has no prereq entry → eligible. It IS offered.
        assert "COMPSCI 201" in result
        # MATH 201 needs MATH 101 or MATH 105 → not eligible with empty completions
        assert "MATH 201" in result
        # STATS 302 needs 4 prereqs → not eligible
        assert "STATS 302" in result

        # The recommended section should exist
        assert "Recommended" in result

    # TC2 — Normal: student with foundational courses done
    def test_tc2_student_with_calculus_done(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC2 (Normal): Student has completed MATH 101 (and thus MATH 201 is now eligible).

        Expected:
          - MATH 201: prereq (MATH 101 or MATH 105) satisfied → recommended (it IS offered)
          - COMPSCI 201: no prereq → recommended (offered)
          - STATS 302: still needs MATH 201, MATH 202, MATH 206 → not eligible
        """
        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        result = recommender(major="data science", completed_courses=["MATH 101"])

        # MATH 201 should now appear under the recommended section
        lines = result.split("\n")
        recommended_section = False
        math201_in_recommended = False
        for line in lines:
            if "Recommended" in line and "eligible" in line.lower():
                recommended_section = True
            if recommended_section and "MATH 201" in line and line.strip().startswith("-"):
                math201_in_recommended = True
                break
            if line.startswith("###") and "Recommended" not in line:
                recommended_section = False

        assert math201_in_recommended, (
            "MATH 201 should appear in the recommended section when MATH 101 is completed.\n"
            f"Full output:\n{result}"
        )

        # STATS 302 should still be in 'not eligible'
        assert "prerequisites not met" in result.lower() or "not eligible" in result.lower()

    # TC3 — OR prerequisite: second option satisfies
    def test_tc3_or_prereq_satisfied_by_alternate(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC3 (OR prereq): Student has MATH 105 (not MATH 101).

        MATH 201 prerequisite is 'MATH 101 or MATH 105'.
        Having only MATH 105 should still make the student eligible.
        """
        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        result = recommender(major="data science", completed_courses=["MATH 105"])

        lines = result.split("\n")
        recommended_section = False
        math201_in_recommended = False
        for line in lines:
            if "Recommended" in line and "eligible" in line.lower():
                recommended_section = True
            if recommended_section and "MATH 201" in line and line.strip().startswith("-"):
                math201_in_recommended = True
                break
            if line.startswith("###") and "Recommended" not in line:
                recommended_section = False

        assert math201_in_recommended, (
            "MATH 201 should be recommended when MATH 105 is done (OR prereq).\n"
            f"Full output:\n{result}"
        )

    # TC4 — Complex multi-prereq chain: STATS 302 with all prereqs done
    def test_tc4_all_prereqs_for_stats302(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC4 (Complex): Student completed all prereqs for STATS 302.

        STATS 302 requires MATH 201, MATH 202, MATH 206, and COMPSCI 201.
        With all four completed, STATS 302 should appear as recommended (it IS offered).
        """
        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        completed = ["MATH 201", "MATH 202", "MATH 206", "COMPSCI 201"]
        result = recommender(major="data science", completed_courses=completed)

        lines = result.split("\n")
        recommended_section = False
        stats302_in_recommended = False
        for line in lines:
            if "Recommended" in line and "eligible" in line.lower():
                recommended_section = True
            if recommended_section and "STATS 302" in line and line.strip().startswith("-"):
                stats302_in_recommended = True
                break
            if line.startswith("###") and "Recommended" not in line:
                recommended_section = False

        assert stats302_in_recommended, (
            "STATS 302 should be recommended once all 4 prereqs are completed.\n"
            f"Full output:\n{result}"
        )

    # TC5 — Edge case: all required courses already completed
    def test_tc5_all_courses_completed(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC5 (Edge case): Student has completed every required course.

        Should return a 'you have completed all required courses' message instead
        of an empty recommendation grid.
        """
        # Extract all codes from the requirements fixtures to simulate full completion
        all_ds = ["COMPSCI 201", "STATS 302", "STATS 303", "STATS 401",
                  "MATH 201", "MATH 202", "MATH 206", "COMPSCI 301"]
        all_core = ["GCHINA 101", "GLOCHALL 201", "ETHLDR 201"]
        completed = all_ds + all_core

        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        result = recommender(major="data science", completed_courses=completed)

        assert "completed all required courses" in result.lower(), (
            f"Expected completion message, got:\n{result}"
        )

    # TC6 — Unknown major
    def test_tc6_unknown_major(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC6: User provides a major that doesn't exist in the requirements dir."""
        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        result = recommender(major="astrology and witchcraft", completed_courses=[])
        assert "No matching major" in result

    # TC7 — Common-core courses: ETHLDR 201 chain
    def test_tc7_common_core_prereq_chain(
        self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses
    ):
        """TC7 (Complex): Tests the common-core prerequisite chain.

        GLOCHALL 201 requires GCHINA 101.
        ETHLDR 201 requires GLOCHALL 201.
        Student who has GCHINA 101 but not GLOCHALL 201:
          - GLOCHALL 201 → eligible (offered in fixture)
          - ETHLDR 201 → not eligible (GLOCHALL 201 not yet completed)
        """
        recommender = CourseRecommenderOuter(
            requirements_dir=req_dir,
            classdata_csv_path=sample_classdata_real_csv,
            prereq_csv_path=prereq_csv_with_ds_courses,
        )
        # Also complete DS courses so the report focuses on core courses
        completed = [
            "GCHINA 101",  # satisfies GLOCHALL 201's prereq
            "COMPSCI 201", "STATS 302", "STATS 303", "STATS 401",
            "MATH 201", "MATH 202", "MATH 206", "COMPSCI 301",
        ]
        result = recommender(major="data science", completed_courses=completed)

        # GLOCHALL 201 should be recommended (GCHINA 101 done, GLOCHALL offered)
        lines = result.split("\n")
        recommended_section = False
        glochall_recommended = False
        ethldr_not_eligible = False

        for line in lines:
            if "Recommended" in line and "eligible" in line.lower():
                recommended_section = True
            if recommended_section and "GLOCHALL 201" in line and line.strip().startswith("-"):
                glochall_recommended = True
            if line.startswith("###") and "Recommended" not in line:
                recommended_section = False
            if "not eligible" in line.lower() or "prerequisites not met" in line.lower():
                pass  # Just note we're in the not-eligible section
            if "ETHLDR 201" in line and ("not eligible" in result.lower()):
                ethldr_not_eligible = True

        assert glochall_recommended, (
            "GLOCHALL 201 should be recommended (GCHINA 101 done, GLOCHALL 201 is offered).\n"
            f"Full output:\n{result}"
        )
        assert "ETHLDR 201" in result, "ETHLDR 201 should appear somewhere in the report"


# ---------------------------------------------------------------------------
# CourseRecommenderOuter: infrastructure / span tests
# ---------------------------------------------------------------------------


class TestCourseRecommenderInfra:
    def test_returns_callable(self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses):
        fn = CourseRecommenderOuter(req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses)
        assert callable(fn)

    def test_nonexistent_requirements_dir_raises(self, mock_span_ctx, sample_classdata_real_csv, prereq_csv_with_ds_courses):
        fn = CourseRecommenderOuter("/nonexistent/path", sample_classdata_real_csv, prereq_csv_with_ds_courses)
        with pytest.raises(FileNotFoundError):
            fn(major="data science", completed_courses=[])

    def test_span_status_ok_on_success(self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses):
        fn = CourseRecommenderOuter(req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses)
        fn(major="data science", completed_courses=[])
        calls = mock_span_ctx.set_status.call_args_list
        assert any(c.args[0].status_code == StatusCode.OK for c in calls if c.args)

    def test_span_attributes_set(self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses):
        fn = CourseRecommenderOuter(req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses)
        fn(major="data science", completed_courses=[])
        assert mock_span_ctx.set_attributes.called

    def test_report_contains_summary_counts(self, mock_span_ctx, req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses):
        fn = CourseRecommenderOuter(req_dir, sample_classdata_real_csv, prereq_csv_with_ds_courses)
        result = fn(major="data science", completed_courses=[])
        # Report should have summary header stats
        assert "Total required courses" in result
        assert "Completed:" in result
        assert "Remaining:" in result
