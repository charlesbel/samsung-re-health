import json
import stat

import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.catalog import CatalogStore, ManifestInfo


def test_catalog_round_trip_is_private(tmp_path):
    path = tmp_path / "catalog.json"
    manifests = [
        ManifestInfo("com.samsung.health.sleep", 6, 6),
        ManifestInfo("com.samsung.health.step_count", 5, 5),
    ]
    store = CatalogStore(path)
    store.save(manifests)
    assert store.load() == manifests
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_catalog_rejects_invalid_manifest_ids(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "manifests": [
                    {
                        "manifest_id": "../../escape",
                        "schema_revision": 1,
                        "manifest_version": 1,
                        "push_id": "",
                    }
                ]
            }
        )
    )
    with pytest.raises(SamsungHealthCloudError, match="manifest"):
        CatalogStore(path).load()


def test_catalog_store_does_not_change_existing_parent_permissions(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    CatalogStore(parent / "catalog.json").save([])
    assert stat.S_IMODE(parent.stat().st_mode) == 0o755
