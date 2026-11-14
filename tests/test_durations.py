import pytest

from ytmcp.durations import parse_duration


@pytest.mark.parametrize("value, expected", [
    ("PT45S", 45),
    ("PT10M", 600),
    ("PT1H", 3600),
    ("PT1H4M30S", 3870),
    ("P1DT2H", 93600),
])
def test_valid(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["", "PT", "P", "10 minutes", "1H30M", "PT-5S"])
def test_invalid(value):
    with pytest.raises(ValueError):
        parse_duration(value)