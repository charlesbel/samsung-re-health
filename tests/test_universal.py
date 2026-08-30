from __future__ import annotations

import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.catalog import ManifestInfo
from samsung_health_cloud.universal import resolve_manifest

MANIFESTS = [
    ManifestInfo("com.samsung.health.exercise", 35, 35),
    ManifestInfo("com.samsung.shealth.exercise", 30, 30),
    ManifestInfo("com.samsung.health.heart_rate", 10, 10),
    ManifestInfo("com.samsung.health.heart_rate_warning", 2, 2),
]


def test_resolve_manifest_accepts_exact_id_and_unique_human_suffix():
    assert (
        resolve_manifest(MANIFESTS, "com.samsung.health.exercise").manifest_id
        == "com.samsung.health.exercise"
    )
    assert resolve_manifest(MANIFESTS, "exercise").manifest_id == "com.samsung.health.exercise"


def test_resolve_manifest_rejects_ambiguous_or_unknown_queries():
    with pytest.raises(SamsungHealthCloudError, match="ambiguous"):
        resolve_manifest(MANIFESTS, "heart")
    with pytest.raises(SamsungHealthCloudError, match="not found"):
        resolve_manifest(MANIFESTS, "glucose_unicorn")
