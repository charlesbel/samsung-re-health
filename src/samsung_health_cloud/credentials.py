from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import platformdirs

from .auth import SamsungHealthCloudError
from .file_lock import secure_read_file

__all__ = [
    "ALLOWED_AUTH_HOST_SUFFIXES",
    "MasterCredentials",
    "default_master_state_path",
    "legacy_find_state_path",
    "load_master_credentials",
    "resolve_master_state_path",
]

ALLOWED_AUTH_HOST_SUFFIXES = ("samsungosp.com", "samsungcloud.com", "samsung.com")
_V1_AUTH_SERVER_PATTERN = re.compile(
    r"^https://(?:(?:[A-Za-z0-9-]+\.)*samsungosp\.com|account\.samsung\.com)/?$"
)


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


def _validate_legacy_auth_url(url: str) -> str:
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


def _validate_master_state_v1(payload: dict) -> MasterCredentials:
    expected_top_keys = {
        "schema",
        "schema_version",
        "generation",
        "created_at",
        "updated_at",
        "account",
        "installation",
        "identity",
    }
    if set(payload.keys()) != expected_top_keys:
        raise SamsungHealthCloudError(
            "Samsung master state v1 has invalid keys (missing or unknown keys)"
        )

    if payload["schema"] != "io.github.charlesbel.samsung-account.master":
        raise SamsungHealthCloudError(
            f"invalid master state schema identifier: {payload['schema']}"
        )
    if payload["schema_version"] != 1:
        raise SamsungHealthCloudError(
            f"unsupported master state schema version: {payload['schema_version']}"
        )
    if not isinstance(payload["generation"], str) or not payload["generation"]:
        raise SamsungHealthCloudError("invalid master state generation")
    if not isinstance(payload["created_at"], (int, float)) or payload["created_at"] < 0:
        raise SamsungHealthCloudError("invalid master state created_at")
    if not isinstance(payload["updated_at"], (int, float)) or payload["updated_at"] < 0:
        raise SamsungHealthCloudError("invalid master state updated_at")

    account = payload["account"]
    if not isinstance(account, dict):
        raise SamsungHealthCloudError("invalid master state account object")
    if set(account.keys()) - {"login_id", "user_id"} != set() or "login_id" not in account:
        raise SamsungHealthCloudError(
            "invalid master state account keys (missing login_id or unknown keys)"
        )
    login_id = account["login_id"]
    if not isinstance(login_id, str) or not login_id:
        raise SamsungHealthCloudError("invalid master state login_id")
    user_id = account.get("user_id")
    if user_id is not None and not isinstance(user_id, str):
        raise SamsungHealthCloudError("invalid master state user_id")

    installation = payload["installation"]
    if not isinstance(installation, dict) or set(installation.keys()) != {"physical_address"}:
        raise SamsungHealthCloudError("invalid master state installation keys")
    physical_address = installation["physical_address"]
    if not isinstance(physical_address, str) or not physical_address:
        raise SamsungHealthCloudError("invalid master state physical_address")

    identity = payload["identity"]
    if not isinstance(identity, dict) or set(identity.keys()) != {
        "auth_server_url",
        "userauth_token",
    }:
        raise SamsungHealthCloudError("invalid master state identity keys")
    userauth_token = identity["userauth_token"]
    if not isinstance(userauth_token, str) or not userauth_token:
        raise SamsungHealthCloudError("invalid master state userauth_token")

    auth_server_url = identity["auth_server_url"]
    if not isinstance(auth_server_url, str) or not auth_server_url:
        raise SamsungHealthCloudError("invalid master state auth_server_url")

    # Strict URL validation matching schema
    if not _V1_AUTH_SERVER_PATTERN.fullmatch(auth_server_url):
        raise SamsungHealthCloudError(
            f"invalid Samsung auth server authority domain: {auth_server_url}"
        )

    parsed = urlparse(auth_server_url)
    if parsed.scheme != "https":
        raise SamsungHealthCloudError("invalid Samsung auth server authority: must be HTTPS")
    if parsed.path not in ("", "/"):
        raise SamsungHealthCloudError("invalid Samsung auth server authority: path must be root")
    if parsed.query or parsed.fragment:
        raise SamsungHealthCloudError(
            "invalid Samsung auth server authority: query/fragment forbidden"
        )
    if parsed.username or parsed.password:
        raise SamsungHealthCloudError("invalid Samsung auth server authority: userinfo forbidden")
    if parsed.port is not None and parsed.port != 443:
        raise SamsungHealthCloudError(
            "invalid Samsung auth server authority: non-443 port forbidden"
        )

    return MasterCredentials(
        token=userauth_token,
        login_id=login_id,
        physical_address=physical_address,
        auth_server_url=auth_server_url,
        user_id=user_id or "",
        generation=payload["generation"],
    )


def load_master_credentials(path: Path) -> MasterCredentials:
    """Read and validate Samsung master credentials from disk with fail-closed security checks."""
    content = secure_read_file(path, require_private=True, lock=True)
    try:
        payload = json.loads(content)
    except ValueError as exc:
        raise SamsungHealthCloudError("unable to parse Samsung master state as JSON") from exc

    if not isinstance(payload, dict):
        raise SamsungHealthCloudError("invalid Samsung master state payload structure")

    # Check if payload is schema-versioned v1
    if (
        payload.get("schema") == "io.github.charlesbel.samsung-account.master"
        or "schema_version" in payload
    ):
        return _validate_master_state_v1(payload)

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

    _validate_legacy_auth_url(auth_server_url)

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
