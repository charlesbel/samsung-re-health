from pathlib import Path

from samsung_health_cloud import (
    DeviceProfile,
    HealthConfig,
    SamsungHealthClient,
    SamsungHealthCloudError,
    SamsungHealthError,
    SamsungHealthLocalClient,
    __version__,
)


def test_package_exports():
    assert HealthConfig is not None
    assert SamsungHealthClient is not None
    assert SamsungHealthLocalClient is not None
    assert issubclass(SamsungHealthCloudError, SamsungHealthError)
    assert DeviceProfile is not None
    assert isinstance(__version__, str) and len(__version__) > 0


def test_local_client_offline_without_credentials(tmp_path: Path):
    # Testing that local client functions in empty environment without network or credentials
    config = HealthConfig(
        cache_path=tmp_path / "test.sqlite3",
        master_state_path=tmp_path / "nonexistent_master.json",
        state_path=tmp_path / "nonexistent_state.json",
    )
    with SamsungHealthLocalClient(config=config) as client:
        status_info = client.cache_status()
        assert "records" in status_info

        types_list = client.types()
        assert isinstance(types_list, list)
        assert len(types_list) > 0  # Loads bundled baseline catalog

        doc = client.doctor()
        assert "cache_db" in doc


def test_exceptions_hierarchy():
    from samsung_health_cloud.exceptions import (
        AuthenticationError,
        DataError,
        NetworkError,
        RateLimitError,
        SchemaError,
        StateError,
        UsageError,
    )

    assert issubclass(AuthenticationError, SamsungHealthError)
    assert issubclass(NetworkError, SamsungHealthError)
    assert issubclass(StateError, SamsungHealthError)
    assert issubclass(UsageError, SamsungHealthError)
    assert issubclass(DataError, SamsungHealthError)
    assert issubclass(SchemaError, SamsungHealthError)
    assert issubclass(RateLimitError, SamsungHealthError)
