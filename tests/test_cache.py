from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from samsung_health_cloud.cache import HealthCache


def envelope(uuid: str, *, start: int, end: int | None = None, update: int | None = None, **values):
    data = {"datauuid": uuid, "start_time": start, "update_time": update or start, **values}
    if end is not None:
        data["end_time"] = end
    return {"data": data, "files": [], "downloadUrls": [], "needToDecrypt": False}


def test_upsert_replaces_same_cloud_document_and_keeps_database_private(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    cache.upsert_documents("com.samsung.health.step_count", [envelope("one", start=1000, count=10)])
    cache.upsert_documents("com.samsung.health.step_count", [envelope("one", start=1000, update=2000, count=25)])

    rows = cache.records("com.samsung.health.step_count", since_ms=0, until_ms=3000)

    assert [row["count"] for row in rows] == [25]
    assert (tmp_path / "health.sqlite3").stat().st_mode & 0o777 == 0o600


def test_records_are_filtered_by_overlap_and_sorted_chronologically(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    cache.upsert_documents(
        "com.samsung.health.sleep",
        [
            envelope("late", start=3000, end=5000),
            envelope("early", start=1000, end=2500),
            envelope("outside", start=6000, end=7000),
        ],
    )

    rows = cache.records("com.samsung.health.sleep", since_ms=2000, until_ms=5500)

    assert [row["datauuid"] for row in rows] == ["early", "late"]


def test_sync_metadata_tracks_freshness_without_storing_tokens(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    cache.mark_synced("com.samsung.health.sleep", schema_revision=18, synced_at=1234, record_count=7)

    status = cache.sync_status("com.samsung.health.sleep")

    assert status == {"last_sync_ms": 1234, "schema_revision": 18, "record_count": 7, "error": None}
    with sqlite3.connect(tmp_path / "health.sqlite3") as db:
        schema = " ".join(row[0] for row in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
    assert "token" not in schema.lower()
