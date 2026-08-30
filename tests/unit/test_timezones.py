from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from samsung_health_cloud import HealthConfig, SamsungHealthLocalClient
from samsung_health_cloud.analysis_engine import period_bounds
from samsung_health_cloud.cache import HealthCache
from samsung_health_cloud.filters import parse_instant_ms


def test_parse_instant_utc_default():
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


def test_dst_transition_bounds_europe_paris():
    paris_tz = ZoneInfo("Europe/Paris")
    utc_tz = ZoneInfo("UTC")

    # Summer date (CEST = UTC+2): 2026-08-28
    summer_day = date(2026, 8, 28)
    s_paris, u_paris = period_bounds("day", summer_day, tz=paris_tz)
    s_utc, u_utc = period_bounds("day", summer_day, tz=utc_tz)

    # In Paris (UTC+2), midnight occurs 2 hours (7,200,000 ms) before UTC midnight
    assert s_utc - s_paris == 2 * 3600 * 1000
    assert u_utc - u_paris == 2 * 3600 * 1000

    # Winter date (CET = UTC+1): 2026-01-15
    winter_day = date(2026, 1, 15)
    s_paris_w, u_paris_w = period_bounds("day", winter_day, tz=paris_tz)
    s_utc_w, u_utc_w = period_bounds("day", winter_day, tz=utc_tz)

    # In Paris winter (UTC+1), midnight occurs 1 hour (3,600,000 ms) before UTC midnight
    assert s_utc_w - s_paris_w == 1 * 3600 * 1000
    assert u_utc_w - u_paris_w == 1 * 3600 * 1000


def test_client_analyze_exercise_and_generic_timezone_propagation(tmp_path: Path):
    db_path = tmp_path / "cache.sqlite3"
    cache = HealthCache(db_path)

    # Insert an exercise record at 2026-08-27 23:00:00 UTC
    # In Europe/Paris (UTC+2), this is 2026-08-28 01:00:00 (inside 2026-08-28 day)
    # In UTC, this is 2026-08-27 23:00:00 (NOT inside 2026-08-28 day)
    event_ms = 1787871600000  # 2026-08-27 23:00:00 UTC
    cache.upsert_documents(
        "com.samsung.health.exercise",
        [
            {
                "data": {
                    "datauuid": "ex-1",
                    "start_time": event_ms,
                    "end_time": event_ms + 1800000,
                    "duration": 1800000,
                    "mean_heart_rate": 130.0,
                    "calorie": 250.0,
                    "distance": 3500.0,
                },
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )

    # Client configured with Europe/Paris
    paris_config = HealthConfig(cache_path=db_path, timezone="Europe/Paris")
    client_paris = SamsungHealthLocalClient(paris_config)

    # Client configured with UTC
    utc_config = HealthConfig(cache_path=db_path, timezone="UTC")
    client_utc = SamsungHealthLocalClient(utc_config)

    # When querying day period with anchored anchor date in analyze:
    # Exercise
    s_paris, u_paris = period_bounds("day", date(2026, 8, 28), tz=ZoneInfo("Europe/Paris"))
    res_paris = client_paris._analysis_engine.exercise(since_ms=s_paris, until_ms=u_paris)
    assert res_paris["events"] == 1

    s_utc, u_utc = period_bounds("day", date(2026, 8, 28), tz=ZoneInfo("UTC"))
    res_utc = client_utc._analysis_engine.exercise(since_ms=s_utc, until_ms=u_utc)
    assert res_utc["events"] == 0
