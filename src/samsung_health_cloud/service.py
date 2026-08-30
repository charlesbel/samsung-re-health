from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .auth import HealthToken
from .credentials import MasterCredentials, load_master_credentials
from .scsp import CloudToken
from .state import HealthState, StateStore

__all__ = [
    "HealthAuthProtocol",
    "MasterCredentials",
    "SamsungHealthService",
    "ScspProtocol",
    "load_master_credentials",
]


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
        credentials = load_master_credentials(self.master_state_path)

        generation_changed = state.master_generation != credentials.generation
        derived_identity_exists = any(
            (
                state.health_access_token,
                state.health_refresh_token,
                state.health_access_expires_at,
                state.health_refresh_expires_at,
                state.cloud_token,
                state.cloud_expires_at,
                state.user_id,
                state.cdid,
                state.registration_id,
            )
        )
        # A missing lineage marker is only safe to adopt for an empty derived state.
        # Existing pre-generation identity may belong to another master account.
        if generation_changed and (state.master_generation or derived_identity_exists):
            state.health_access_token = ""
            state.health_refresh_token = ""
            state.health_access_expires_at = 0
            state.health_refresh_expires_at = 0
            state.cloud_token = ""
            state.cloud_expires_at = 0
            state.user_id = ""
            state.cdid = ""
            state.registration_id = ""

        # Adopt and persist the current generation only after stale derived state is cleared.
        state.master_generation = credentials.generation
        if generation_changed:
            self.store.save(state)

        if not state.cdid:
            state.cdid = secrets.token_hex(32)
            self.store.save(state)

        if (
            not state.health_access_token
            or state.health_access_expires_at <= now + 60
            or not state.user_id
        ):
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
