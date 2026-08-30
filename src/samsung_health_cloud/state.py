from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Iterator

from .auth import SamsungHealthCloudError
from .file_lock import InterprocessLock, secure_atomic_write, secure_read_file

__all__ = ["HealthState", "StateStore"]


@dataclass(slots=True)
class HealthState:
    health_access_token: str = ""
    health_refresh_token: str = ""
    health_access_expires_at: int = 0
    health_refresh_expires_at: int = 0
    cloud_token: str = ""
    cloud_expires_at: int = 0
    user_id: str = ""
    cdid: str = ""
    registration_id: str = ""

    def __repr__(self) -> str:
        secret_fields = {
            "health_access_token",
            "health_refresh_token",
            "cloud_token",
            "user_id",
            "cdid",
            "registration_id",
        }
        values = []
        for item in fields(self):
            value = (
                "<redacted>"
                if item.name in secret_fields and getattr(self, item.name)
                else getattr(self, item.name)
            )
            values.append(f"{item.name}={value!r}")
        return f"HealthState({', '.join(values)})"


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.lock")

    @contextmanager
    def locked(self) -> Iterator[None]:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.lock_path, flags, 0o600)
        lock = InterprocessLock(fd, exclusive=True)
        try:
            if hasattr(os, "fchmod") and os.name != "nt":
                os.fchmod(fd, 0o600)
            lock.acquire()
            yield
        finally:
            lock.release()
            os.close(fd)

    def load(self) -> HealthState:
        if not self.path.exists():
            return HealthState()
        content = secure_read_file(self.path, require_private=True, lock=True)
        try:
            payload = json.loads(content)
        except ValueError as exc:
            raise SamsungHealthCloudError("unable to read Samsung Health state") from exc

        if not isinstance(payload, dict):
            raise SamsungHealthCloudError("unable to read Samsung Health state")

        allowed = {item.name for item in fields(HealthState)}
        selected = {key: value for key, value in payload.items() if key in allowed}
        string_fields = {
            "health_access_token",
            "health_refresh_token",
            "cloud_token",
            "user_id",
            "cdid",
            "registration_id",
        }
        integer_fields = {
            "health_access_expires_at",
            "health_refresh_expires_at",
            "cloud_expires_at",
        }
        if any(not isinstance(selected.get(key, ""), str) for key in string_fields):
            raise SamsungHealthCloudError("Samsung Health state contains invalid field types")
        if any(
            not isinstance(selected.get(key, 0), int)
            or isinstance(selected.get(key, 0), bool)
            or selected.get(key, 0) < 0
            for key in integer_fields
        ):
            raise SamsungHealthCloudError("Samsung Health state contains invalid field types")
        return HealthState(**selected)

    def save(self, state: HealthState) -> None:
        content = json.dumps(asdict(state), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        secure_atomic_write(self.path, content, file_mode=0o600, dir_mode=0o700)
