"""Shared fixtures for ChatDKU tool tests."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture()
def mock_span_ctx(monkeypatch):
    """Mock span_ctx_start so no real tracer/Phoenix is needed.

    Patches at every import site since each tool module binds the name at import time.
    Returns the mock span for assertions on set_attributes / set_status.
    """
    mock_span = MagicMock()

    @contextmanager
    def fake_span_ctx_start(name, kind, parent_context=None):
        yield mock_span

    targets = [
        "chatdku.core.utils.span_ctx_start",
        "chatdku.core.tools.course_schedule.span_ctx_start",
        "chatdku.core.tools.course_recommender.span_ctx_start",
        "chatdku.core.tools.get_prerequisites.span_ctx_start",
        "chatdku.core.tools.major_requirements.span_ctx_start",
        "chatdku.core.tools.syllabi_tool.query_curriculum_db.span_ctx_start",
        "chatdku.core.tools.retriever.base_retriever.span_ctx_start",
    ]
    for target in targets:
        try:
            monkeypatch.setattr(target, fake_span_ctx_start)
        except (AttributeError, ImportError):
            pass  # module not yet imported — safe to skip

    return mock_span


@pytest.fixture()
def mock_get_current_span(monkeypatch):
    """Mock get_current_span for llama_index_tools which uses it directly."""
    mock_span = MagicMock()
    monkeypatch.setattr(
        "chatdku.core.tools.llama_index_tools.get_current_span", lambda: mock_span
    )
    return mock_span


@pytest.fixture()
def sample_classdata_csv(tmp_path):
    """Create a temporary class schedule CSV with representative data."""
    csv_path = tmp_path / "classdata.csv"
    df = pd.DataFrame(
        {
            "Subject": ["COMPSCI", "COMPSCI", "MATH", "BIOL", "CHINESE"],
            "Catalog": ["101", "201", "201", "305", "101A"],
            "Section": ["01", "01", "01", "01", "01"],
            "Component": ["LEC", "LEC", "LEC", "LAB", "LEC"],
            "Instructor": [
                "Alice Smith",
                "Bob Jones",
                "Carol Lee",
                "Dave Kim",
                "Eve Wu",
            ],
            "Days": ["MWF", "TTh", "MWF", "TTh", "MWF"],
            "Start Time": ["09:00", "10:30", "11:00", "14:00", "13:00"],
            "End Time": ["09:50", "11:45", "11:50", "15:15", "13:50"],
            "Enrollment": [30, 25, 40, 15, 20],
        }
    )
    df.to_csv(csv_path, index=False)
    return str(csv_path)


@pytest.fixture()
def sample_classdata_real_csv(tmp_path):
    """Classdata CSV matching the actual cleaned_classdata.csv column layout.

    Uses Mon/Tues/Wed/Thurs/Fri boolean columns and Mtg Start/Mtg End for times,
    matching what clean_classdata.py produces on the server.
    """
    csv_path = tmp_path / "classdata_real.csv"
    df = pd.DataFrame(
        {
            "Course ID": [1001, 1002, 1003, 1004, 1005],
            "Term": [2268] * 5,
            "Session": ["7W1", "7W1", "7W2", "7W1", "7W2"],
            "Section": ["001", "001", "001", "001", "001"],
            "Subject": ["COMPSCI", "MATH", "MATH", "STATS", "GLOCHALL"],
            "Catalog": ["201", "201", "202", "302", "201"],
            "Descr": [
                "Intro to Programming and Data Structures",
                "Multivariable Calculus",
                "Linear Algebra",
                "Principles of Machine Learning",
                "Global Challenges",
            ],
            "Class Nbr": [100, 101, 102, 103, 104],
            "Enrollment Status": ["Open"] * 5,
            "Class Status": ["Active"] * 5,
            "Enrollment Capacity": [40] * 5,
            "Wait List Capacity": [8] * 5,
            "Enrollment Total": [20] * 5,
            "Wait List Total": [0] * 5,
            "Seats Open": ["20/40"] * 5,
            "Waitlist Open": ["8/8"] * 5,
            "Attributes": [""] * 5,
            "Prgrss Unt": [4.0] * 5,
            "Grading": ["GRD"] * 5,
            "Start Date": ["08/25/2026"] * 5,
            "End Date": ["10/08/2026"] * 5,
            "Mtg Start": [
                "9:00:00.000000AM",
                "10:00:00.000000AM",
                "2:00:00.000000PM",
                "8:00:00.000000AM",
                "9:00:00.000000AM",
            ],
            "Mtg End": [
                "9:50:00.000000AM",
                "10:50:00.000000AM",
                "2:50:00.000000PM",
                "8:50:00.000000AM",
                "9:50:00.000000AM",
            ],
            "Mon": ["Y", "Y", "N", "Y", "Y"],
            "Tues": ["N", "N", "Y", "N", "N"],
            "Wed": ["Y", "Y", "N", "Y", "Y"],
            "Thurs": ["N", "N", "Y", "N", "N"],
            "Fri": ["Y", "Y", "N", "Y", "Y"],
            "Room No": ["IB1001"] * 5,
            "Instructor": [
                "Smith,Alice",
                "Jones,Bob",
                "Lee,Carol",
                "Kim,Dave",
                "Wu,Eve",
            ],
        }
    )
    df.to_csv(csv_path, index=False)
    return str(csv_path)


@pytest.fixture()
def sample_prereq_csv(tmp_path):
    """Create a temporary prerequisites CSV with UTF-16LE encoding.

    Column layout matches positional access in get_prereq:
      col 0: ID
      col 1: Effective Date (MM/DD/YYYY)
      col 2: Subject
      col 3: Catalog
      cols 4-12: padding
      col 13: Description (prerequisite text)
    """
    csv_path = tmp_path / "prereq.csv"
    rows = [
        # COMPSCI 201 with prereqs, two rows with different dates
        [
            1,
            "01/15/2023",
            "COMPSCI",
            "201",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Prereq: COMPSCI 101",
        ],
        [
            2,
            "09/01/2024",
            "COMPSCI",
            "201",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Prereq: COMPSCI 101 or COMPSCI 102",
        ],
        # MATH 201 with prereqs
        [
            3,
            "03/10/2024",
            "MATH",
            "201",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Prereq: MATH 101",
        ],
        # BIOL 305 with empty description
        [4, "06/01/2024", "BIOL", "305", "", "", "", "", "", "", "", "", "", ""],
    ]
    columns = [f"col{i}" for i in range(14)]
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(csv_path, index=False, encoding="utf-16le")
    return str(csv_path)
