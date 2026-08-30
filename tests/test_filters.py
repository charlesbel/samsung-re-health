import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from samsung_health_cloud.filters import filter_records, parse_instant_ms


def test_parse_instant_and_filter_records_by_overlapping_interval():
    paris = ZoneInfo("Europe/Paris")
    expected = int(datetime(2026, 1, 1, tzinfo=paris).timestamp() * 1000)
    assert parse_instant_ms("2026-01-01", timezone="Europe/Paris") == expected

    records = [
        {
            "data": {
                "start_time": expected - 1000,
                "end_time": expected + 1000,
                "count": 1,
            }
        },
        {
            "data": {
                "start_time": expected + 2000,
                "end_time": expected + 3000,
                "count": 2,
            }
        },
        {"data": {"create_time": expected + 4000, "count": 3}},
    ]
    selected = list(filter_records(records, since_ms=expected, until_ms=expected + 2500))
    assert [record["data"]["count"] for record in selected] == [1, 2]

    with pytest.raises(ValueError, match="ISO-8601"):
        parse_instant_ms("not-a-date")


@pytest.mark.parametrize(
    "record, message",
    [
        ({"data": {"start_time": math.nan, "end_time": 1}}, "finite"),
        ({"data": {"start_time": 2, "end_time": 1}}, "inverted"),
        ({"data": {"count": 3}}, "timestamp"),
    ],
)
def test_time_filter_rejects_ambiguous_or_invalid_records(record, message):
    with pytest.raises(ValueError, match=message):
        list(filter_records([record], since_ms=0, until_ms=10))


def test_time_filter_accepts_finite_numeric_strings():
    records = [{"data": {"start_time": "1", "end_time": "2", "count": 1}}]
    assert list(filter_records(records, since_ms=0, until_ms=10)) == records
