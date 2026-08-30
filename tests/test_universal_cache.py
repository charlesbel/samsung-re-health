from __future__ import annotations

from pathlib import Path

from samsung_health_cloud.cache import HealthCache


def test_envelopes_preserve_every_cloud_field_and_return_newest_first(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    manifest = "com.samsung.health.exercise"
    first = {
        "data": {"datauuid": "one", "start_time": 1000, "nested": {"unknown": [1, 2]}},
        "files": [{"name": "route.bin", "custom": "kept"}],
        "downloadUrls": ["https://example.invalid/signed"],
        "needToDecrypt": True,
        "futureEnvelopeField": {"also": "kept"},
    }
    second = {"data": {"datauuid": "two", "start_time": 2000}, "files": [], "downloadUrls": [], "needToDecrypt": False}
    cache.upsert_documents(manifest, [first, second])

    rows = cache.envelopes(manifest, since_ms=0, until_ms=3000, limit=1)

    assert rows == [second]
    assert cache.envelopes(manifest, since_ms=0, until_ms=1500, limit=10) == [first]


def test_manifest_inventory_reports_all_fields_and_attachment_counts(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    manifest = "com.samsung.health.exercise"
    cache.upsert_documents(
        manifest,
        [
            {
                "data": {"datauuid": "one", "start_time": 1000, "heart_rate": 72, "nested": {"x": 1}},
                "files": [{"name": "one"}],
                "downloadUrls": ["https://example.invalid/one"],
                "needToDecrypt": True,
            },
            {
                "data": {"datauuid": "two", "start_time": 2000, "calorie": 10},
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            },
        ],
    )

    inventory = cache.manifest_inventory(manifest)

    assert inventory["records"] == 2
    assert inventory["encrypted_records"] == 1
    assert inventory["records_with_files"] == 1
    assert inventory["records_with_download_urls"] == 1
    assert inventory["fields"] == ["calorie", "datauuid", "heart_rate", "nested", "start_time"]


def test_global_inventory_counts_every_manifest_and_full_envelope_feature(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    cache.upsert_documents(
        "com.samsung.health.exercise",
        [{"data": {"datauuid": "one", "start_time": 1}, "files": [{"name": "x"}], "downloadUrls": [], "needToDecrypt": False}],
    )
    cache.upsert_documents(
        "com.samsung.health.sleep",
        [{"data": {"datauuid": "two", "start_time": 2}, "files": [], "downloadUrls": ["https://example.invalid/x"], "needToDecrypt": True}],
    )

    inventory = cache.global_inventory()

    assert inventory == {
        "manifests_with_records": 2,
        "records": 2,
        "encrypted_records": 1,
        "records_with_files": 1,
        "records_with_download_urls": 1,
    }
