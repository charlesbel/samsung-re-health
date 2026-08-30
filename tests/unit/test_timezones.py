from datetime import datetime
from zoneinfo import ZoneInfo

from samsung_health_cloud.filters import parse_instant_ms


def test_parse_instant_utc_default():
    # 2026-08-30 00:00:00 UTC
    ms = parse_instant_ms("2026-08-30")
    dt = datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("UTC"))
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 30
    assert dt.hour == 0


def test_parse_instant_with_specific_timezone():
    ms_tokyo = parse_instant_ms("2026-08-30", timezone="Asia/Tokyo")
    ms_utc = parse_instant_ms("2026-08-30", timezone="UTC")
    # Tokyo is UTC+9, so midnight in Tokyo is 9 hours earlier than UTC midnight
    assert ms_tokyo == ms_utc - (9 * 3600 * 1000)
