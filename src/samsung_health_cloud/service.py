from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .auth import HealthToken, SamsungHealthCloudError
from .scsp import CloudToken
from .state import HealthState, StateStore


@dataclass(frozen=True, slots=True, repr=False)
class MasterCredentials:
    token: str
    login_id: str
    physical_address: str
    auth_server_url: str
    user_id: str

    def __repr__(self) -> str:
        return "MasterCredentials(token='<redacted>', login_id='<redacted>')"


def load_master_credentials(path: Path) -> MasterCredentials:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SamsungHealthCloudError(
            "unable to read Samsung Find authentication state"
        ) from exc
    tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
    account = payload.get("account") if isinstance(payload.get("account"), dict) else {}
    token = (
        payload.get("userauth_token")
        or tokens.get("persistent_master_token")
        or payload.get("persistent_master_token")
    )
    login_id = (
        payload.get("login_id")
        or payload.get("account_email")
        or payload.get("email")
        or account.get("email")
    )
    physical_address = payload.get("device_id")
    auth_server_url = payload.get("auth_server_url")
    user_id = payload.get("user_id") or ""
    required = (token, login_id, physical_address, auth_server_url)
    if not all(isinstance(value, str) and value for value in required):
        raise SamsungHealthCloudError(
            "Samsung Find state is missing required authentication fields"
        )
    return MasterCredentials(
        token=token,
        login_id=login_id,
        physical_address=physical_address,
        auth_server_url=auth_server_url,
        user_id=user_id if isinstance(user_id, str) else "",
    )


class HealthAuthProtocol(Protocol):
    def issue(self, **kwargs: str) -> HealthToken: ...


class ScspProtocol(Protocol):
    def register(self, **kwargs: str) -> str: ...
    def issue_token(self, **kwargs: str) -> CloudToken: ...


class SamsungHealthService:
    def __init__(
        self,
        *,
        store: StateStore,
        master_state_path: Path,
        health_auth: HealthAuthProtocol,
        scsp: ScspProtocol,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.master_state_path = master_state_path
        self.health_auth = health_auth
        self.scsp = scsp
        self.now = now

    def initialize(self) -> HealthState:
        with self.store.locked():
            return self._initialize_locked()

    def _initialize_locked(self) -> HealthState:
        state = self.store.load()
        now = int(self.now())
        if not state.cdid:
            state.cdid = secrets.token_hex(32)
            self.store.save(state)

        if (
            not state.health_access_token
            or state.health_access_expires_at <= now + 60
            or not state.user_id
        ):
            credentials = load_master_credentials(self.master_state_path)
            health = self.health_auth.issue(
                master_token=credentials.token,
                login_id=credentials.login_id,
                physical_address=credentials.physical_address,
                auth_server_url=credentials.auth_server_url,
                user_id=credentials.user_id,
            )
            state.health_access_token = health.access_token
            state.health_refresh_token = health.refresh_token
            state.user_id = health.user_id
            state.health_access_expires_at = now + health.expires_in
            state.health_refresh_expires_at = now + health.refresh_expires_in
            state.cloud_token = ""
            state.cloud_expires_at = 0
            self.store.save(state)

        identity_args = {
            "health_access_token": state.health_access_token,
            "user_id": state.user_id,
            "cdid": state.cdid,
        }
        if not state.registration_id:
            state.registration_id = self.scsp.register(**identity_args)
            self.store.save(state)
        if not state.cloud_token or state.cloud_expires_at <= now + 60:
            cloud = self.scsp.issue_token(**identity_args)
            state.cloud_token = cloud.authorization
            state.cloud_expires_at = cloud.expires_at
            self.store.save(state)

        return state
