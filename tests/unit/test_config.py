from pathlib import Path
from zoneinfo import ZoneInfo

from samsung_health_cloud.config import HealthConfig


def test_config_defaults():
    config = HealthConfig()
    assert config.timezone == ZoneInfo("UTC")
    assert isinstance(config.master_state_path, Path)
    assert isinstance(config.state_path, Path)
    assert isinstance(config.cache_path, Path)
    assert isinstance(config.catalog_path, Path)
    assert config.device_profile.model_name != ""
    assert "HERMES" not in config.device_profile.alias
    assert "Charles" not in config.device_profile.alias


def test_config_custom_timezone_and_paths(tmp_path: Path):
    custom_master = tmp_path / "custom_master.json"
    config = HealthConfig(
        master_state_path=custom_master,
        timezone="Europe/Paris",
    )
    assert config.master_state_path == custom_master
    assert config.timezone == ZoneInfo("Europe/Paris")


def test_config_from_env(monkeypatch, tmp_path: Path):
    env_master = tmp_path / "env_master.json"
    monkeypatch.setenv("SAMSUNG_ACCOUNT_MASTER_STATE", str(env_master))
    monkeypatch.setenv("SAMSUNG_HEALTH_TIMEZONE", "Asia/Tokyo")

    config = HealthConfig.from_env()
    assert config.master_state_path == env_master
    assert config.timezone == ZoneInfo("Asia/Tokyo")
