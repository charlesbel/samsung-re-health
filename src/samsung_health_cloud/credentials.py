from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import platformdirs

from .auth import SamsungHealthCloudError

ALLOWED_AUTH_HOST_SUFFIXES = ("samsungosp.com", "samsungcloud.com", "samsung.com")


@dataclass(frozen=True, slots=True, repr=False)
class MasterCredentials:
    token: str
    login_id: str
    physical_address: str
    auth_server_url: str
    user_id: str = ""
    generation: str = ""

    def __repr__(self) -> str:
        return "MasterCredentials(token='<redacted>', login_id='<redacted>')"


def _validate_auth_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SamsungHealthCloudError("invalid Samsung auth server authority: must be HTTPS")
    if not parsed.hostname:
        raise SamsungHealthCloudError("invalid Samsung auth server authority: missing hostname")
    if parsed.username or parsed.password:
        raise SamsungHealthCloudError("invalid Samsung auth server authority: userinfo forbidden")
    hostname = parsed.hostname.lower()
    if not any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in ALLOWED_AUTH_HOST_SUFFIXES
    ):
        raise SamsungHealthCloudError(
            f"invalid Samsung auth server authority: untrusted host domain '{hostname}'"
        )
    return url


def load_master_credentials(path: Path) -> MasterCredentials:
    if not path.exists():
        raise SamsungHealthCloudError("Samsung master state file does not exist")
    if path.is_symlink():
        raise SamsungHealthCloudError("Samsung master state must not be a symlink")

    try:
        file_stat = path.stat()
    except OSError as exc:
        raise SamsungHealthCloudError("unable to inspect Samsung master state") from exc

    if hasattr(os, "getuid") and file_stat.st_uid != os.getuid():
        raise SamsungHealthCloudError("Samsung master state has an unexpected owner")

    # On POSIX systems, ensure group and others have no permissions
    if hasattr(stat, "S_IMODE") and os.name != "nt" and stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise SamsungHealthCloudError("Samsung master state permissions must be private")

    try:
        content = path.read_text(encoding="utf-8")
        payload = json.loads(content)
    except (OSError, ValueError) as exc:
        raise SamsungHealthCloudError("unable to read Samsung master state") from exc

    if not isinstance(payload, dict):
        raise SamsungHealthCloudError("invalid Samsung master state payload structure")

    # Check if payload is schema-versioned v1
    if (
        payload.get("schema") == "io.github.charlesbel.samsung-account.master"
        or "schema_version" in payload
    ):
        version = payload.get("schema_version")
        if version != 1:
            raise SamsungHealthCloudError(
                f"unsupported Samsung master state schema version: {version}"
            )

        account = payload.get("account") if isinstance(payload.get("account"), dict) else {}
        installation = (
            payload.get("installation") if isinstance(payload.get("installation"), dict) else {}
        )
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}

        token = identity.get("userauth_token")
        login_id = account.get("login_id")
        physical_address = installation.get("physical_address")
        auth_server_url = identity.get("auth_server_url")
        user_id = account.get("user_id") or ""
        generation = payload.get("generation") or ""

        required = (token, login_id, physical_address, auth_server_url, generation)
        if not all(isinstance(val, str) and val for val in required):
            raise SamsungHealthCloudError("Samsung master state v1 is missing required fields")

        _validate_auth_url(auth_server_url)

        return MasterCredentials(
            token=token,
            login_id=login_id,
            physical_address=physical_address,
            auth_server_url=auth_server_url,
            user_id=user_id if isinstance(user_id, str) else "",
            generation=generation,
        )

    # Legacy fallback format
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

    if not all(isinstance(val, str) and val for val in required):
        raise SamsungHealthCloudError(
            "Samsung master state is missing required authentication fields"
        )

    _validate_auth_url(auth_server_url)

    return MasterCredentials(
        token=token,
        login_id=login_id,
        physical_address=physical_address,
        auth_server_url=auth_server_url,
        user_id=user_id if isinstance(user_id, str) else "",
        generation="",
    )


def default_master_state_path() -> Path:
    return Path(platformdirs.user_config_dir("samsung-account")) / "master.json"


def legacy_find_state_path() -> Path:
    return Path.home() / ".config" / "samsung-find" / "state.json"


def resolve_master_state_path(
    injected: Path | str | None = None,
    cli_override: Path | str | None = None,
) -> Path:
    if injected is not None:
        return Path(injected)
    if cli_override is not None:
        return Path(cli_override)
    env_path = os.environ.get("SAMSUNG_ACCOUNT_MASTER_STATE")
    if env_path:
        return Path(env_path)

    default_path = default_master_state_path()
    if not default_path.exists():
        legacy = legacy_find_state_path()
        if legacy.exists():
            print(
                "Warning: using legacy Samsung Find state at ~/.config/samsung-find/state.json. "
                "Migrate to neutral master state v1 (~/.config/samsung-account/master.json).",
                file=sys.stderr,
            )
            return legacy

    return default_path
