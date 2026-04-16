import pandas as pd
from chatdku.core.tools.course_schedule import (
    _lookup,
    _parse_course,
)


def test_parse_course():
    assert _parse_course("COMPSCI 101") == ("COMPSCI", "101")
    assert _parse_course("COMPSCI101") == ("COMPSCI", "101")
    assert _parse_course("COMPSCI-101") == ("COMPSCI", "101")
    assert _parse_course("Chinese 101A") == ("CHINESE", "101A")
    assert _parse_course("COMPSCI101A") == ("COMPSCI", "101A")


def test_lookup():
    df = pd.DataFrame(
        {
            "Subject": ["COMPSCI", "MATH"],
            "Catalog": ["101", "201"],
        }
    )
    assert _lookup("ASTROLOGY 1239", df) == []
