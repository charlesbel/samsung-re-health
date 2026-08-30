from __future__ import annotations

from datetime import date
from pathlib import Path

from samsung_health_cloud.analytics import HealthAnalytics
from samsung_health_cloud.cache import HealthCache


def add(cache: HealthCache, manifest: str, uuid: str, **data):
    cache.upsert_documents(
        manifest,
        [
            {
                "data": {"datauuid": uuid, **data},
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )


def test_daily_steps_returns_consolidated_value_not_raw_records(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    # Midnight in Europe/Paris on 2026-08-28.
    day_ms = 1787868000000
    add(
        cache,
        "com.samsung.shealth.step_daily_trend",
        "a",
        day_time=day_ms,
        count=4210,
        distance=3200.0,
        calorie=155.0,
    )
    add(
        cache,
        "com.samsung.shealth.step_daily_trend",
        "b",
        day_time=day_ms,
        count=5870,
        distance=4490.0,
        calorie=214.0,
    )
    add(
        cache,
        "com.samsung.shealth.step_daily_trend",
        "all",
        day_time=day_ms,
        count=5000,
        distance=4000.0,
        calorie=190.0,
        source_type=-2,
    )

    report = HealthAnalytics(cache).steps(date(2026, 8, 28))

    assert {key: report[key] for key in ("date", "steps", "distance_m", "calories_kcal")} == {
        "date": "2026-08-28",
        "steps": 5000,
        "distance_m": 4000.0,
        "calories_kcal": 190.0,
    }
    assert report["calculations"]["record_selection"]["rule"].startswith("source_type == -2")


def test_sleep_merges_overlapping_segments_and_reports_efficiency(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    add(
        cache,
        "com.samsung.health.sleep",
        "a",
        start_time=1787864400000,
        end_time=1787886000000,
        efficiency=90.0,
    )
    add(
        cache,
        "com.samsung.health.sleep",
        "b",
        start_time=1787884200000,
        end_time=1787893200000,
        efficiency=80.0,
    )

    report = HealthAnalytics(cache).sleep(date(2026, 8, 28))

    assert report["date"] == "2026-08-28"
    assert report["duration_minutes"] == 480
    assert report["source_records"] == 2
    assert report["merged_sleep_intervals"] == 1
    assert "sessions" not in report
    assert report["average_reported_efficiency_percent"] == 85.0
    assert "average_efficiency_percent" not in report


def test_heart_rate_returns_final_statistics(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    for index, value in enumerate((60.0, 72.0, 90.0)):
        add(
            cache,
            "com.samsung.health.heart_rate",
            str(index),
            start_time=1787880000000 + index,
            heart_rate=value,
        )

    report = HealthAnalytics(cache).heart_rate(date(2026, 8, 28))

    assert {
        key: report[key]
        for key in (
            "date",
            "samples",
            "arithmetic_mean_bpm",
            "minimum_bpm",
            "maximum_bpm",
        )
    } == {
        "date": "2026-08-28",
        "samples": 3,
        "arithmetic_mean_bpm": 74.0,
        "minimum_bpm": 60.0,
        "maximum_bpm": 90.0,
    }
    assert report["calculations"]["arithmetic_mean_bpm"]["source_field"].endswith(".heart_rate")
