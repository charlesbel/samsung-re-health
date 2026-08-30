import json
from contextlib import contextmanager

from samsung_health_cloud.auth import HealthToken
from samsung_health_cloud.scsp import CloudToken
from samsung_health_cloud.service import SamsungHealthService, load_master_credentials
from samsung_health_cloud.state import StateStore


class AssertingLockedStore(StateStore):
    active = False

    @contextmanager
    def locked(self):
        self.active = True
        try:
            yield
        finally:
            self.active = False

    def load(self):
        assert self.active, "state load must happen under the interprocess lock"
        return super().load()

    def save(self, state):
        assert self.active, "state save must happen under the interprocess lock"
        return super().save(state)


class FakeHealthAuth:
    def issue(self, **kwargs):
        assert kwargs["master_token"] == "master-secret"
        assert kwargs["login_id"] == "person@example.com"
        assert kwargs["physical_address"] == "physical-id"
        assert kwargs["auth_server_url"] == "https://eu-auth2.samsungosp.com"
        return HealthToken("health-secret", "refresh-secret", "uid-1", 100, 200, "bearer")


class FakeScsp:
    def register(self, **kwargs):
        assert kwargs["health_access_token"] == "health-secret"
        assert kwargs["user_id"] == "uid-1"
        assert kwargs["cdid"]
        return "registration-1"

    def issue_token(self, **kwargs):
        return CloudToken("Bearer cloud-secret", 2_000_000_000)


def test_service_initializes_from_samsung_find_state_without_exposing_master(tmp_path):
    master_path = tmp_path / "find-state.json"
    master_path.write_text(
        json.dumps(
            {
                "login_id": "person@example.com",
                "userauth_token": "master-secret",
                "device_id": "physical-id",
                "auth_server_url": "https://eu-auth2.samsungosp.com",
            }
        )
    )
    credentials = load_master_credentials(master_path)
    assert "master-secret" not in repr(credentials)
    assert "person@example.com" not in repr(credentials)
    assert "uid-1" not in repr(HealthToken("access", "refresh", "uid-1", 1, 2, "bearer"))

    store = AssertingLockedStore(tmp_path / "health-state.json")
    service = SamsungHealthService(
        store=store,
        master_state_path=master_path,
        health_auth=FakeHealthAuth(),
        scsp=FakeScsp(),
        now=lambda: 1_000,
    )
    state = service.initialize()

    assert state.user_id == "uid-1"
    assert state.registration_id == "registration-1"
    assert state.health_access_expires_at == 1_100
    assert state.health_refresh_expires_at == 1_200
    assert state.cloud_expires_at == 2_000_000_000
    assert len(state.cdid) == 64
    assert StateStore.load(store) == state
    assert "health-secret" not in repr(state)


def test_service_checkpoints_successful_stages_before_a_later_failure(tmp_path):
    master_path = tmp_path / "find-state.json"
    master_path.write_text(
        json.dumps(
            {
                "login_id": "person@example.com",
                "userauth_token": "master-secret",
                "device_id": "physical-id",
                "auth_server_url": "https://eu-auth2.samsungosp.com",
            }
        )
    )

    class FailingAfterRegistration(FakeScsp):
        def issue_token(self, **kwargs):
            raise RuntimeError("temporary token failure")

    store = StateStore(tmp_path / "health-state.json")
    service = SamsungHealthService(
        store=store,
        master_state_path=master_path,
        health_auth=FakeHealthAuth(),
        scsp=FailingAfterRegistration(),
        now=lambda: 1_000,
    )
    try:
        service.initialize()
    except RuntimeError as exc:
        assert str(exc) == "temporary token failure"
    else:
        raise AssertionError("the simulated token failure must propagate")

    checkpoint = store.load()
    assert checkpoint.cdid
    assert checkpoint.health_access_token == "health-secret"
    assert checkpoint.registration_id == "registration-1"
    assert not checkpoint.cloud_token
