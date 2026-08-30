from pathlib import Path

import pytest

from samsung_health_cloud import (
    HealthConfig,
    SamsungHealthClient,
    SamsungHealthLocalClient,
    UsageError,
)
from samsung_health_cloud.cache import HealthCache


def test_local_client_analyze_sleep(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    cache = HealthCache(db_path)
    cache.upsert_documents(
        "com.samsung.health.sleep",
        [
            {
                "data": {
                    "datauuid": "sleep-1",
                    "start_time": 1700000000000,
                    "end_time": 1700028800000,
                    "efficiency": 88,
                },
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )
    config = HealthConfig(cache_path=db_path)
    with SamsungHealthLocalClient(config=config) as client:
        analysis = client.analyze("sleep", latest=True)
        assert analysis["available"] is True
        assert analysis["reported_efficiency_percent"] == 88


def test_local_client_analyze_activity_period(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    cache = HealthCache(db_path)
    cache.upsert_documents(
        "com.samsung.shealth.step_daily_trend",
        [
            {
                "data": {
                    "datauuid": "step-1",
                    "day_time": 1700000000000,
                    "update_time": 1700000001000,
                    "source_type": -2,
                    "count": 7500,
                    "distance": 5200.0,
                    "calorie": 250.0,
                },
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )
    config = HealthConfig(cache_path=db_path)
    with SamsungHealthLocalClient(config=config) as client:
        analysis = client.analyze("activity", all_history=True)
        assert analysis["steps"] == 7500
        assert analysis["days_with_data"] == 1


def test_local_client_analyze_option_exclusivity(tmp_path: Path):
    config = HealthConfig(cache_path=tmp_path / "test.sqlite3")
    with SamsungHealthLocalClient(config=config) as client:
        with pytest.raises(UsageError, match="mutually exclusive"):
            client.analyze("activity", latest=True, all_history=True)

        with pytest.raises(UsageError, match="does not support --latest"):
            client.analyze("activity", latest=True)

        with pytest.raises(UsageError, match="only supports --latest"):
            client.analyze("sleep", period="week")


def test_local_client_read_data(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    cache = HealthCache(db_path)
    cache.upsert_documents(
        "com.samsung.health.weight",
        [
            {
                "data": {
                    "datauuid": "w-1",
                    "start_time": 1700000000000,
                    "weight": 70.5,
                },
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )
    config = HealthConfig(cache_path=db_path)
    with SamsungHealthLocalClient(config=config) as client:
        records = client.read_data("weight", limit=10)
        assert len(records) == 1
        assert records[0]["weight"] == 70.5


def test_local_client_summary(tmp_path: Path):
    config = HealthConfig(cache_path=tmp_path / "test.sqlite3")
    with SamsungHealthLocalClient(config=config) as client:
        summ = client.summary(day="2026-08-30")
        assert summ["date"] == "2026-08-30"
        assert "steps" in summ
        assert "sleep" in summ
        assert "heart_rate" in summ
        assert "latest_weight" in summ


def test_online_client_status(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        '{"user_id": "test-uid", "health_access_expires_at": 2000000000}',
        encoding="utf-8",
    )
    state_file.chmod(0o600)
    config = HealthConfig(state_path=state_file, cache_path=tmp_path / "cache.sqlite3")
    with SamsungHealthClient(config=config) as client:
        st = client.status()
        assert st["user_id_present"] is True
        assert st["health_access_expires_at"] == 2000000000
        assert st["health_access_expired"] is False
