"""Synthetic regression for schema revisions rejected by the cloud service."""

from dataclasses import replace

import httpx
import pytest

from samsung_health_cloud.cache import HealthCache
from samsung_health_cloud.catalog import CatalogStore, ManifestInfo
from samsung_health_cloud.data import CloudDataClient
from samsung_health_cloud.sync import CacheSynchronizer

SCHEMA_UPDATES = [
    ("com.samsung.health.antioxidant", (1,), 2),
    ("com.samsung.health.exercise", (17, 35), 36),
    ("com.samsung.health.sleep", (18,), 19),
    ("com.samsung.health.weight", (11, 13), 12),
    ("com.samsung.shealth.cycle.prediction", (4,), 5),
    ("com.samsung.shealth.mood", (1,), 2),
    ("com.samsung.shealth.program.sleep_coaching.session", (4,), 5),
    ("com.samsung.shealth.sleep_combined", (8,), 9),
    ("com.samsung.shealth.tracker.pedometer_day_summary", (6,), 7),
]


@pytest.mark.parametrize("manifest_id,old_revisions,new_revision", SCHEMA_UPDATES)
def test_bundled_catalog_sync_uses_supported_schema(
    tmp_path, manifest_id, old_revisions, new_revision
):
    manifests = CatalogStore(tmp_path / "missing.json").load()
    target = next((m for m in manifests if m.manifest_id == manifest_id), None)
    assert target is not None

    def handler(request):
        status = 200 if int(request.url.params["schemaRevision"]) == new_revision else 400
        return httpx.Response(status, json={"documents": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        cache = HealthCache(tmp_path / "synthetic.sqlite3")
        syncer = CacheSynchronizer(cache, CloudDataClient(http), cloud_authorization="synthetic")
        result = syncer.sync([target], since_ms=0, until_ms=None, force=True)
    assert result["failed_manifests"] == 0
    assert result["synced_manifests"] == 1


@pytest.mark.parametrize("manifest_id,old_revisions,new_revision", SCHEMA_UPDATES)
def test_existing_catalog_corrects_only_known_stale_revisions(
    tmp_path, manifest_id, old_revisions, new_revision
):
    path = tmp_path / "catalog.json"
    store = CatalogStore(path)
    for old_revision in old_revisions:
        original = ManifestInfo(manifest_id, old_revision, 42, "synthetic-routing")
        store.save([original])
        before = path.read_bytes()
        assert store.load() == [replace(original, schema_revision=new_revision)]
        assert path.read_bytes() == before
    custom = ManifestInfo(manifest_id, new_revision + 10, 42, "synthetic-routing")
    store.save([custom])
    assert store.load() == [custom]
