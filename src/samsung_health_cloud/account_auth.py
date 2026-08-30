from __future__ import annotations

import secrets
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import httpx

from .account_paths import resolve_account_master_path, resolve_pending_path
from .account_storage import read_json, secure_unlink, verify_no_symlink_components, write_json
from .capture_redirect import is_expected_redirect_uri
from .constants import AUTH_CLIENT_ID, ENTRY_POINT_URL, REDIRECT_URI
from .credentials import (
    _validate_master_state_v1,
    load_master_credentials,
)
from .crypto import code_challenge, decrypt_auth_value, encrypt_svc_param, random_urlsafe
from .exceptions import AuthenticationError, SamsungHealthCloudError

_PENDING_MAX_AGE_SECONDS = 15 * 60
_MASTER_SCHEMA = "io.github.charlesbel.samsung-account.master"


def _validate_response_url(
    response: httpx.Response,
    *,
    expected_url: str,
    operation: str,
) -> None:
    if response.history or response.is_redirect:
        raise SamsungHealthCloudError(f"{operation} redirect not allowed")
    actual = response.url
    expected = httpx.URL(expected_url)
    if actual.userinfo or actual.fragment:
        raise SamsungHealthCloudError(f"{operation} response URL contains forbidden components")
    if (
        actual.scheme != "https"
        or actual.host != expected.host
        or actual.port not in (None, 443)
        or actual.path != expected.path
        or actual.query != expected.query
    ):
        raise SamsungHealthCloudError(f"{operation} response URL is from an untrusted authority")


def _validate_sign_in_uri(value: Any) -> str:
    if not isinstance(value, str):
        raise SamsungHealthCloudError("Samsung entry point omitted sign-in URI")
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise SamsungHealthCloudError(
            "Samsung entry point returned an invalid sign-in URI"
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "account.samsung.com"
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or not parsed.path.startswith("/accounts/")
        or parsed.query
        or parsed.fragment
    ):
        raise SamsungHealthCloudError("Samsung entry point returned an untrusted sign-in URI")
    return urllib.parse.urlunsplit(("https", "account.samsung.com", parsed.path, "", ""))


def _trusted_auth_server_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Samsung returned an invalid authentication server") from exc
    host = (parsed.hostname or "").lower()
    trusted = (
        host == "account.samsung.com"
        or host == "samsungosp.com"
        or host.endswith(".samsungosp.com")
    )
    if (
        parsed.scheme != "https"
        or not trusted
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise AuthenticationError("Samsung returned an untrusted authentication server")
    return f"https://{host}"


class AccountBootstrap:
    """Independent Samsung Account master-state-v1 bootstrap for samsung-re-health."""

    def __init__(
        self,
        *,
        master_path: str | Path | None = None,
        pending_path: str | Path | None = None,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.master_path = resolve_account_master_path(master_path)
        self.pending_path = (
            verify_no_symlink_components(pending_path)
            if pending_path is not None
            else resolve_pending_path(self.master_path)
        )
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=False)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> AccountBootstrap:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def start(self, country: str = "us", locale: str = "en-US") -> str:
        try:
            response = self.client.get(ENTRY_POINT_URL, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise SamsungHealthCloudError(
                "Samsung Account entry point network request failed"
            ) from exc
        _validate_response_url(response, expected_url=ENTRY_POINT_URL, operation="entry point")
        self._raise_success(response, "entry point")
        entry = self._json(response, "entry point")

        device_id = secrets.token_hex(16)
        if self.master_path.exists():
            existing = load_master_credentials(self.master_path)
            device_id = existing.physical_address

        state = random_urlsafe(15)[:20]
        verifier = random_urlsafe(32)[:43]
        payload: dict[str, object] = {
            "clientId": AUTH_CLIENT_ID,
            "code_challenge": code_challenge(verifier),
            "code_challenge_method": "S256",
            "competitorDeviceYNFlag": "Y",
            "countryCode": country.lower(),
            "deviceInfo": "Google|com.android.chrome",
            "deviceModelID": "Pixel 8 Pro",
            "deviceName": "Google Pixel 8 Pro",
            "deviceOSVersion": "35",
            "devicePhysicalAddressText": f"ANID:{device_id}",
            "deviceType": "APP",
            "deviceUniqueID": device_id,
            "redirect_uri": REDIRECT_URI,
            "replaceableClientConnectYN": "N",
            "replaceableClientId": "",
            "replaceableDevicePhysicalAddressText": "",
            "responseEncryptionType": "1",
            "responseEncryptionYNFlag": "Y",
            "scope": "",
            "state": state,
            "svcIptLgnID": "",
            "iosYNFlag": "Y",
        }
        try:
            encrypted = encrypt_svc_param(
                payload,
                int(entry["chkDoNum"]),
                str(entry["pkiPublicKey"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SamsungHealthCloudError(
                "Samsung entry point returned invalid key material"
            ) from exc
        write_json(
            self.pending_path,
            {
                "state": state,
                "code_verifier": verifier,
                "device_id": device_id,
                "created_at": int(time.time()),
            },
        )
        sign_in = _validate_sign_in_uri(entry.get("signInURI"))
        return f"{sign_in}?locale={urllib.parse.quote(locale, safe='')}&svcParam={encrypted}&mode=C"

    def complete(self, redirect_uri: str) -> dict[str, bool | int]:
        pending = read_json(self.pending_path)
        state = ""
        verifier = ""
        device_id = ""
        try:
            created_at = pending["created_at"]
            if isinstance(created_at, bool):
                raise TypeError
            age = time.time() - float(created_at)
            state = pending["state"]
            verifier = pending["code_verifier"]
            device_id = pending["device_id"]
            if not all(isinstance(item, str) and item for item in (state, verifier, device_id)):
                raise TypeError
        except (KeyError, TypeError, ValueError):
            age = float("inf")
        if age < -60 or age > _PENDING_MAX_AGE_SECONDS:
            secure_unlink(self.pending_path)
            raise AuthenticationError("Pending Samsung authentication has expired")
        if not is_expected_redirect_uri(redirect_uri):
            raise AuthenticationError(
                "Samsung redirect does not match the configured callback target"
            )

        parsed = urllib.parse.urlsplit(redirect_uri)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if parsed.fragment:
            params.update(urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True))

        def one(name: str) -> str:
            values = params.get(name, [])
            if len(values) != 1 or not values[0]:
                raise AuthenticationError(f"Samsung redirect is missing or duplicates {name}")
            return values[0]

        try:
            response_key = decrypt_auth_value(one("state"), state)
            auth_server = decrypt_auth_value(one("auth_server_url"), response_key)
            code = decrypt_auth_value(one("code"), response_key)
            login_id = decrypt_auth_value(one("retValue"), response_key)
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("Unable to decrypt Samsung redirect") from exc
        auth_server = _trusted_auth_server_url(auth_server)
        authenticate_url = f"{auth_server}/auth/oauth2/authenticate"
        try:
            response = self.client.post(
                authenticate_url,
                data={
                    "grant_type": "authorization_code",
                    "serviceType": "M",
                    "client_id": AUTH_CLIENT_ID,
                    "code": code,
                    "code_verifier": verifier,
                    "username": login_id,
                    "physical_address_text": device_id,
                },
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise SamsungHealthCloudError("master authentication network request failed") from exc
        _validate_response_url(
            response,
            expected_url=authenticate_url,
            operation="master authentication",
        )
        self._raise_success(response, "master authentication")
        master_response = self._json(response, "master authentication")
        token = master_response.get("userauth_token") or master_response.get("userAuthToken")
        user_id = master_response.get("userId") or master_response.get("user_id")
        if not isinstance(token, str) or not token or not isinstance(user_id, str) or not user_id:
            raise AuthenticationError("Samsung response omitted master user token or user id")

        now = time.time()
        created = now
        if self.master_path.exists():
            current = read_json(self.master_path)
            _validate_master_state_v1(current)
            created = float(current["created_at"])
        master_state = {
            "schema": _MASTER_SCHEMA,
            "schema_version": 1,
            "generation": str(uuid.uuid4()),
            "created_at": created,
            "updated_at": now,
            "account": {"login_id": login_id, "user_id": user_id},
            "installation": {"physical_address": device_id},
            "identity": {"auth_server_url": auth_server, "userauth_token": token},
        }
        _validate_master_state_v1(master_state)
        write_json(self.master_path, master_state)
        secure_unlink(self.pending_path)
        return self.public_status()

    def public_status(self) -> dict[str, bool | int]:
        if not self.master_path.exists():
            return {
                "authenticated": False,
                "device_id_present": False,
                "schema_version": 1,
                "user_id_present": False,
            }
        credentials = load_master_credentials(self.master_path)
        return {
            "authenticated": bool(credentials.token),
            "device_id_present": bool(credentials.physical_address),
            "schema_version": 1,
            "user_id_present": bool(credentials.user_id),
        }

    @staticmethod
    def _json(response: httpx.Response, operation: str) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError as exc:
            raise SamsungHealthCloudError(f"Samsung {operation} returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise SamsungHealthCloudError(f"Samsung {operation} returned an invalid payload")
        return value

    @staticmethod
    def _raise_success(response: httpx.Response, operation: str) -> None:
        if not response.is_success:
            raise SamsungHealthCloudError(
                f"Samsung {operation} failed with HTTP {response.status_code}"
            )
