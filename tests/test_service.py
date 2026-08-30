import json
from contextlib import contextmanager

from samsung_health_cloud.auth import HealthToken
from samsung_health_cloud.scsp import CloudToken
from samsung_health_cloud.service import SamsungHealthService, load_master_credentials
from samsung_health_cloud.state import HealthState, StateStore


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
        assert kwargs["master_token"] == "synthetic-test-master-token"
        assert kwargs["login_id"] == "person@example.com"
        assert kwargs["physical_address"] == "physical-id"
        assert kwargs["auth_server_url"] == "https://eu-auth2.samsungosp.com"
        return HealthToken(
            "synthetic-test-health-token",
            "synthetic-test-refresh-token",
            "uid-1",
            100,
            200,
            "bearer",
        )


class FakeScsp:
    def register(self, **kwargs):
        assert kwargs["health_access_token"] == "synthetic-test-health-token"
        assert kwargs["user_id"] == "uid-1"
        assert kwargs["cdid"]
        return "registration-1"

    def issue_token(self, **kwargs):
        return CloudToken("Bearer synthetic-test-cloud-token", 2_000_000_000)


def test_service_initializes_from_samsung_find_state_without_exposing_master(tmp_path):
    master_path = tmp_path / "find-state.json"
    master_path.write_text(
        json.dumps(
            {
                "login_id": "person@example.com",
                "userauth_token": "synthetic-test-master-token",
                "device_id": "physical-id",
                "auth_server_url": "https://eu-auth2.samsungosp.com",
            }
        )
    )
    credentials = load_master_credentials(master_path)
    assert "synthetic-test-master-token" not in repr(credentials)
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
    assert "synthetic-test-health-token" not in repr(state)


def test_service_checkpoints_successful_stages_before_a_later_failure(tmp_path):
    master_path = tmp_path / "find-state.json"
    master_path.write_text(
        json.dumps(
            {
                "login_id": "person@example.com",
                "userauth_token": "synthetic-test-master-token",
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
    assert checkpoint.health_access_token == "synthetic-test-health-token"
    assert checkpoint.registration_id == "registration-1"
    assert not checkpoint.cloud_token


def test_service_rotates_credentials_on_generation_mismatch(tmp_path):
    master_path = tmp_path / "master.json"
    master_path.write_text(
        json.dumps(
            {
                "schema": "io.github.charlesbel.samsung-account.master",
                "schema_version": 1,
                "generation": "generation-1",
                "created_at": 100,
                "updated_at": 100,
                "account": {"login_id": "person@example.com"},
                "installation": {"physical_address": "physical-id"},
                "identity": {
                    "auth_server_url": "https://account.samsung.com",
                    "userauth_token": "synthetic-test-master-token",
                },
            }
        ),
        encoding="utf-8",
    )
    master_path.chmod(0o600)

    class AnyScsp:
        def register(self, **kwargs):
            return "reg-1"

        def issue_token(self, **kwargs):
            return CloudToken("Bearer test", 2_000_000_000)

    class_any_scsp = AnyScsp

    class CountingAuth:
        count = 0

        def issue(self, **kwargs):
            self.count += 1
            return HealthToken(f"token-v{self.count}", "ref", "uid-1", 100, 200, "bearer")

    store = StateStore(tmp_path / "health-state.json")
    auth = CountingAuth()
    service = SamsungHealthService(
        store=store,
        master_state_path=master_path,
        health_auth=auth,
        scsp=class_any_scsp(),
        now=lambda: 1_000,
    )
    state1 = service.initialize()
    assert state1.master_generation == "generation-1"
    assert state1.health_access_token == "token-v1"
    assert auth.count == 1

    # Second initialize with same generation -> no re-issue
    state2 = service.initialize()
    assert state2.health_access_token == "token-v1"
    assert auth.count == 1

    # Rotate master state generation
    master_path.write_text(
        json.dumps(
            {
                "schema": "io.github.charlesbel.samsung-account.master",
                "schema_version": 1,
                "generation": "generation-2",
                "created_at": 200,
                "updated_at": 200,
                "account": {"login_id": "person@example.com"},
                "installation": {"physical_address": "physical-id"},
                "identity": {
                    "auth_server_url": "https://account.samsung.com",
                    "userauth_token": "synthetic-test-master-token",
                },
            }
        ),
        encoding="utf-8",
    )

    state3 = service.initialize()
    assert state3.master_generation == "generation-2"
    assert state3.health_access_token == "token-v2"
    assert auth.count == 2


def test_service_reinitializes_derived_identity_when_generation_is_missing(tmp_path):
    master_path = tmp_path / "master.json"
    master_path.write_text(
        json.dumps(
            {
                "schema": "io.github.charlesbel.samsung-account.master",
                "schema_version": 1,
                "generation": "generation-current",
                "created_at": 100,
                "updated_at": 100,
                "account": {"login_id": "person@example.com"},
                "installation": {"physical_address": "physical-id"},
                "identity": {
                    "auth_server_url": "https://account.samsung.com",
                    "userauth_token": "synthetic-test-master-token",
                },
            }
        ),
        encoding="utf-8",
    )
    master_path.chmod(0o600)

    stale_cdid = "stale-derived-cdid"
    store = StateStore(tmp_path / "health-state.json")
    store.save(
        HealthState(
            health_access_token="stale-health-access",
            health_refresh_token="stale-health-refresh",
            health_access_expires_at=2_000_000_000,
            health_refresh_expires_at=2_000_000_000,
            cloud_token="stale-cloud-token",
            cloud_expires_at=2_000_000_000,
            user_id="stale-user-id",
            cdid=stale_cdid,
            registration_id="stale-registration-id",
            master_generation="",
        )
    )

    class ReissuingAuth:
        count = 0

        def issue(self, **kwargs):
            self.count += 1
            return HealthToken("fresh-access", "fresh-refresh", "fresh-user", 100, 200, "bearer")

    class ReissuingScsp:
        def register(self, **kwargs):
            assert kwargs["cdid"] != stale_cdid
            assert kwargs["health_access_token"] == "fresh-access"
            assert kwargs["user_id"] == "fresh-user"
            return "fresh-registration"

        def issue_token(self, **kwargs):
            assert kwargs["cdid"] != stale_cdid
            return CloudToken("Bearer fresh-cloud", 2_000_000_000)

    auth = ReissuingAuth()
    state = SamsungHealthService(
        store=store,
        master_state_path=master_path,
        health_auth=auth,
        scsp=ReissuingScsp(),
        now=lambda: 1_000,
    ).initialize()

    assert auth.count == 1
    assert state.master_generation == "generation-current"
    assert state.health_access_token == "fresh-access"
    assert state.health_refresh_token == "fresh-refresh"
    assert state.user_id == "fresh-user"
    assert state.cdid != stale_cdid
    assert state.registration_id == "fresh-registration"
    assert state.cloud_token == "Bearer fresh-cloud"
