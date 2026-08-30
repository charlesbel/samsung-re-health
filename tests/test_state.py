import fcntl
import os
import stat

import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.state import HealthState, StateStore


def test_state_store_writes_atomically_with_private_permissions_and_redacted_repr(
    tmp_path,
):
    path = tmp_path / "state.json"
    state = HealthState(
        health_access_token="synthetic-test-health-token",
        health_refresh_token="synthetic-test-refresh-token",
        cloud_token="synthetic-test-cloud-token",
        user_id="user-id",
        cdid="client-device-id",
        registration_id="registration-id",
    )

    store = StateStore(path)
    store.save(state)
    restored = store.load()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o600
    assert restored == state
    rendered = repr(restored)
    assert "synthetic-test-health-token" not in rendered
    assert "synthetic-test-refresh-token" not in rendered
    assert "synthetic-test-cloud-token" not in rendered
    assert "user-id" not in rendered
    assert "client-device-id" not in rendered
    assert "registration-id" not in rendered
    assert "<redacted>" in rendered


def test_state_store_rejects_overpermissive_parent_permissions(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    with pytest.raises(SamsungHealthCloudError, match="parent directory permissions"):
        StateStore(parent / "state.json").save(HealthState())


def test_state_store_holds_an_interprocess_lock(tmp_path):
    store = StateStore(tmp_path / "state.json")
    with store.locked():
        competing_fd = os.open(store.lock_path, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(competing_fd)


def test_state_store_transaction_allows_unlocked_and_nested_calls(tmp_path):
    store = StateStore(tmp_path / "state.json")
    with store.locked():
        # Load from transaction
        state = store._load_unlocked()
        assert state == HealthState()
        state.cdid = "tx-cdid"
        store._save_unlocked(state)

        # Public methods are reentrant for the same thread under transaction
        reloaded = store.load()
        assert reloaded.cdid == "tx-cdid"
        reloaded.user_id = "tx-user"
        store.save(reloaded)

    final = store.load()
    assert final.cdid == "tx-cdid"
    assert final.user_id == "tx-user"


def test_state_store_rejects_corrupt_or_overpermissive_state(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not-json")
    path.chmod(0o600)
    with pytest.raises(SamsungHealthCloudError, match="state"):
        StateStore(path).load()

    path.write_text("{}")
    path.chmod(0o644)
    with pytest.raises(SamsungHealthCloudError, match="permissions"):
        StateStore(path).load()
