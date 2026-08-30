from pathlib import Path

import pytest

from samsung_health_cloud import HealthConfig, SamsungHealthClient, SamsungHealthLocalClient
from samsung_health_cloud.exceptions import UsageError


def test_read_data_argument_validation(tmp_path: Path):
    client = SamsungHealthLocalClient(HealthConfig(cache_path=tmp_path / "cache.sqlite3"))

    # limit bounds
    with pytest.raises(UsageError, match="limit"):
        client.read_data("sleep", limit=0)

    with pytest.raises(UsageError, match="limit"):
        client.read_data("sleep", limit=10001)

    # offset bounds
    with pytest.raises(UsageError, match="offset"):
        client.read_data("sleep", offset=-1)

    # since > until
    with pytest.raises(UsageError, match="since"):
        client.read_data("sleep", since="2026-08-30", until="2026-08-01")


def test_sync_argument_validation(tmp_path: Path):
    # Tests run without master credentials because validation fails BEFORE service initialization
    client = SamsungHealthClient(HealthConfig(master_state_path=tmp_path / "nonexistent.json"))

    # Conflicting manifest_id and all_types
    with pytest.raises(UsageError, match="all_types"):
        client.sync(manifest_id="sleep", all_types=True)

    # days out of bounds
    with pytest.raises(UsageError, match="days"):
        client.sync(days=0)

    with pytest.raises(UsageError, match="days"):
        client.sync(days=4000)

    # all_history combined with explicit days
    with pytest.raises(UsageError, match="all_history"):
        client.sync(all_history=True, days=30)


def test_analyze_argument_validation(tmp_path: Path):
    client = SamsungHealthLocalClient(HealthConfig(cache_path=tmp_path / "cache.sqlite3"))

    # Invalid compare value
    with pytest.raises(UsageError, match="compare"):
        client.analyze("activity", compare="invalid_value")

    # Invalid period value
    with pytest.raises(UsageError, match="period"):
        client.analyze("activity", period="century")

    # Multiple selectors
    with pytest.raises(UsageError, match="mutually exclusive"):
        client.analyze("activity", period="week", latest=True)
