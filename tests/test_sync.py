from __future__ import annotations

from pathlib import Path

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.cache import HealthCache
from samsung_health_cloud.catalog import ManifestInfo
from samsung_health_cloud.sync import CacheSynchronizer


class FakeDataClient:
    def __init__(self):
        self.calls = []

    def iter_documents(self, **kwargs):
        self.calls.append(kwargs)
        yield {
            "data": {
                "datauuid": "one",
                "start_time": 1000,
                "update_time": 2000,
                "count": 42,
            },
            "files": [],
            "downloadUrls": [],
            "needToDecrypt": False,
        }


def test_sync_fetches_requested_range_and_populates_cache(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    client = FakeDataClient()
    manifest = ManifestInfo(
        "com.samsung.health.step_count",
        schema_revision=5,
        manifest_version=4,
        push_id="push",
    )
    synchronizer = CacheSynchronizer(
        cache, client, cloud_authorization="redacted", now_ms=lambda: 10_000
    )

    result = synchronizer.sync([manifest], since_ms=500, until_ms=3000)

    assert result["synced_manifests"] == 1
    assert result["fetched_records"] == 1
    assert cache.total_records() == 1
    assert client.calls[0]["start_time"] == 500
    assert client.calls[0]["end_time"] == 3000


def test_fresh_sync_is_skipped_unless_forced(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    client = FakeDataClient()
    manifest = ManifestInfo(
        "com.samsung.health.step_count",
        schema_revision=5,
        manifest_version=4,
        push_id="push",
    )
    cache.mark_synced(manifest.manifest_id, schema_revision=5, synced_at=9_500, record_count=1)
    synchronizer = CacheSynchronizer(
        cache, client, cloud_authorization="redacted", now_ms=lambda: 10_000
    )

    result = synchronizer.sync([manifest], since_ms=0, until_ms=3000, max_age_ms=1000)

    assert result["skipped_fresh"] == 1
    assert client.calls == []


def test_legacy_404_manifest_is_reported_unavailable_not_as_sync_failure(
    tmp_path: Path,
):
    class MissingDataClient:
        def iter_documents(self, **kwargs):
            raise SamsungHealthCloudError("document GET failed with HTTP 404")
            yield

    cache = HealthCache(tmp_path / "health.sqlite3")
    manifest = ManifestInfo("com.samsung.shealth.sleep", schema_revision=13, manifest_version=11)
    synchronizer = CacheSynchronizer(
        cache,
        MissingDataClient(),
        cloud_authorization="redacted",
        now_ms=lambda: 10_000,
    )

    result = synchronizer.sync([manifest], since_ms=None, until_ms=3000)

    assert result["failed_manifests"] == 0
    assert result["unavailable_manifests"] == 1
    assert cache.sync_status(manifest.manifest_id)["error"] == "unavailable: HTTP 404"


def test_full_history_sync_prunes_documents_no_longer_present_upstream(tmp_path: Path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    manifest = ManifestInfo("com.samsung.health.step_count", schema_revision=5, manifest_version=4)
    cache.upsert_documents(
        manifest.manifest_id,
        [
            {
                "data": {"datauuid": "stale", "start_time": 1},
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )
    client = FakeDataClient()
    synchronizer = CacheSynchronizer(
        cache, client, cloud_authorization="redacted", now_ms=lambda: 10_000
    )

    synchronizer.sync([manifest], since_ms=None, until_ms=3000, force=True)

    rows = cache.records(manifest.manifest_id, since_ms=0, until_ms=3000)
    assert [row["datauuid"] for row in rows] == ["one"]
