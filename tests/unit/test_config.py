from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from samsung_health_cloud.config import HealthConfig


def test_config_defaults():
    config = HealthConfig()
    assert config.timezone == ZoneInfo("UTC")
    assert isinstance(config.master_state_path, Path)
    assert isinstance(config.state_path, Path)
    assert isinstance(config.cache_path, Path)
    assert isinstance(config.catalog_path, Path)
    assert config.device_profile.model_name != ""
    assert config.device_profile.alias == "Samsung Health Cloud Client"


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


def test_config_precedence_arg_over_env_over_default(monkeypatch, tmp_path: Path):
    env_cache = tmp_path / "env_cache.sqlite3"
    arg_cache = tmp_path / "arg_cache.sqlite3"
    monkeypatch.setenv("SAMSUNG_HEALTH_CACHE", str(env_cache))
    monkeypatch.setenv("SAMSUNG_HEALTH_TIMEZONE", "Asia/Tokyo")

    # When arg is provided, it wins over env
    config = HealthConfig(cache_path=arg_cache, timezone="Europe/London")
    assert config.cache_path == arg_cache
    assert config.timezone == ZoneInfo("Europe/London")

    # When arg is omitted, env wins over default
    config2 = HealthConfig()
    assert config2.cache_path == env_cache
    assert config2.timezone == ZoneInfo("Asia/Tokyo")


def test_config_timeout_validation():
    from samsung_health_cloud.exceptions import UsageError

    with pytest.raises(UsageError, match="timeout"):
        HealthConfig(timeout=0)

    with pytest.raises(UsageError, match="timeout"):
        HealthConfig(timeout=-5.0)

    with pytest.raises(UsageError, match="timeout"):
        HealthConfig(timeout=500.0)
