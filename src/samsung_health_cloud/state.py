from __future__ import annotations

import json
import fcntl
import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .auth import SamsungHealthCloudError


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
            "health_access_token", "health_refresh_token", "cloud_token",
            "user_id", "cdid", "registration_id",
        }
        values = []
        for item in fields(self):
            value = "<redacted>" if item.name in secret_fields and getattr(self, item.name) else getattr(self, item.name)
            values.append(f"{item.name}={value!r}")
        return f"HealthState({', '.join(values)})"


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.lock")

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.lock_path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def load(self) -> HealthState:
        if not self.path.exists():
            return HealthState()
        if self.path.is_symlink():
            raise SamsungHealthCloudError("Samsung Health state must not be a symlink")
        try:
            file_stat = self.path.stat()
        except OSError:
            raise SamsungHealthCloudError("unable to inspect Samsung Health state")
        if file_stat.st_uid != os.getuid():
            raise SamsungHealthCloudError("Samsung Health state has an unexpected owner")
        if stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise SamsungHealthCloudError("Samsung Health state permissions must be private")
        payload: object | None = None
        failed = False
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failed = True
        if failed or not isinstance(payload, dict):
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
        integer_fields = {"health_access_expires_at", "health_refresh_expires_at", "cloud_expires_at"}
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
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(asdict(state), stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)
