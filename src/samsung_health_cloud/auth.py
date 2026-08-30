from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

HEALTH_CLIENT_ID = "1y90e30264"


from .exceptions import SamsungHealthCloudError


def safe_http_call(
    operation: str, call: Callable[[], httpx.Response]
) -> httpx.Response:
    response: httpx.Response | None = None
    failed = False
    try:
        response = call()
    except httpx.HTTPError:
        failed = True
    if failed:
        raise SamsungHealthCloudError(f"{operation} network request failed")
    if response is None:
        raise SamsungHealthCloudError(f"{operation} network request failed")
    return response


@dataclass(slots=True, repr=False)
class HealthToken:
    access_token: str
    refresh_token: str
    user_id: str
    expires_in: int
    refresh_expires_in: int
    token_type: str

    def __repr__(self) -> str:
        return (
            "HealthToken(access_token='<redacted>', refresh_token='<redacted>', "
            "user_id='<redacted>', "
            f"expires_in={self.expires_in!r}, "
            f"refresh_expires_in={self.refresh_expires_in!r}, token_type={self.token_type!r})"
        )


class HealthAuth:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def issue(
        self,
        *,
        auth_server_url: str,
        master_token: str,
        login_id: str,
        user_id: str | None = None,
        verifier: str | None = None,
        physical_address: str | None = None,
    ) -> HealthToken:
        verifier = verifier or secrets.token_urlsafe(64)
        physical_address = (
            physical_address or base64.b64encode(secrets.token_bytes(18)).decode()
        )
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        params = {
            "response_type": "code",
            "serviceType": "M",
            "client_id": HEALTH_CLIENT_ID,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "childAccountSupported": "Y",
            "userauth_token": master_token,
            "physical_address_text": physical_address,
            "login_id": login_id,
        }
        parsed = urlparse(auth_server_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (
            host == "samsungosp.com" or host.endswith(".samsungosp.com")
        ):
            raise SamsungHealthCloudError("untrusted Samsung authentication domain")
        auth_server_url = auth_server_url.rstrip("/")
        response = safe_http_call(
            "authorize",
            lambda: self.client.get(
                f"{auth_server_url}/auth/oauth2/v2/authorize",
                params=params,
                headers={"Accept": "application/json"},
            ),
        )
        payload = self._json(response, "authorize")
        code = payload.get("code")
        auth_data = payload.get("auth_data")
        response_user_id = (
            auth_data.get("userId") if isinstance(auth_data, dict) else None
        )
        user_id = response_user_id or user_id
        if (
            not isinstance(code, str)
            or not code
            or not isinstance(user_id, str)
            or not user_id
        ):
            raise SamsungHealthCloudError("authorize response missing code or user id")

        response = safe_http_call(
            "token",
            lambda: self.client.post(
                f"{auth_server_url}/auth/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": HEALTH_CLIENT_ID,
                    "client_secret": "",
                    "physical_address_text": physical_address,
                    "code_verifier": verifier,
                },
                headers={"Accept": "application/json"},
            ),
        )
        token_payload = self._json(response, "token")
        try:
            return HealthToken(
                access_token=str(token_payload["access_token"]),
                refresh_token=str(token_payload["refresh_token"]),
                user_id=user_id,
                expires_in=int(token_payload["expires_in"]),
                refresh_expires_in=int(token_payload["refresh_token_expires_in"]),
                token_type=str(token_payload.get("token_type", "bearer")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SamsungHealthCloudError(
                "token response missing expected fields"
            ) from exc

    @staticmethod
    def _json(response: httpx.Response, operation: str) -> dict[str, Any]:
        if response.status_code != 200:
            raise SamsungHealthCloudError(
                f"{operation} failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SamsungHealthCloudError(f"{operation} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SamsungHealthCloudError(f"{operation} returned an invalid payload")
        return payload
