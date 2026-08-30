from pathlib import Path

from samsung_health_cloud import HealthConfig, SamsungHealthLocalClient
from samsung_health_cloud.catalog import load_bundled_manifests
from samsung_health_cloud.universal import resolve_manifest


def test_load_bundled_manifests_has_standard_types():
    manifests = load_bundled_manifests()
    assert len(manifests) >= 10
    ids = {m.manifest_id for m in manifests}
    assert "com.samsung.health.sleep" in ids
    assert "com.samsung.health.heart_rate" in ids
    assert "com.samsung.health.oxygen_saturation" in ids
    assert "com.samsung.shealth.step_daily_trend" in ids
    assert "com.samsung.health.exercise" in ids
    assert "com.samsung.health.weight" in ids
    # Ensure no push_id was leaked into bundled runtime catalog
    for m in manifests:
        assert m.push_id == ""


def test_empty_home_environment_resolves_and_runs_doctor(tmp_path: Path, monkeypatch):
    empty_home = tmp_path / "empty_home"
    empty_home.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(empty_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(empty_home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(empty_home / ".local" / "share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(empty_home / ".local" / "state"))

    config = HealthConfig(
        master_state_path=empty_home / ".config" / "samsung-account" / "master.json",
        state_path=empty_home
        / ".local"
        / "state"
        / "samsung-health-cloud"
        / "state.json",
        cache_path=empty_home
        / ".local"
        / "share"
        / "samsung-health-cloud"
        / "health.sqlite3",
        catalog_path=empty_home / ".config" / "samsung-health-cloud" / "manifests.json",
    )

    with SamsungHealthLocalClient(config=config) as client:
        # Types work without local manifests.json
        types = client.types()
        assert len(types) >= 10

        # Manifest resolution works for human queries
        manifests = client.catalog_store.load()
        resolved_sleep = resolve_manifest(manifests, "sleep")
        assert resolved_sleep.manifest_id == "com.samsung.health.sleep"

        resolved_weight = resolve_manifest(manifests, "weight")
        assert resolved_weight.manifest_id == "com.samsung.health.weight"

        doc = client.doctor()
        assert doc["catalog_count"] >= 10
        assert doc["catalog_present"] is True
