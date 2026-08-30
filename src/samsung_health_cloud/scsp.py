from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .auth import (
    HEALTH_CLIENT_ID,
    SamsungHealthCloudError,
    _validate_response_url,
    safe_http_call,
)
from .models import DeviceProfile

__all__ = [
    "APP_VERSION",
    "PLAY_URL",
    "SCSP_VERSION",
    "CloudToken",
    "DeviceProfile",
    "ScspIdentity",
]

PLAY_URL = "https://play.samsungcloud.com"
APP_VERSION = "7.00.6.003"
SCSP_VERSION = "1.0.1105"


@dataclass(frozen=True, slots=True, repr=False)
class CloudToken:
    authorization: str
    expires_at: int

    def __repr__(self) -> str:
        return f"CloudToken(authorization='<redacted>', expires_at={self.expires_at!r})"


class ScspIdentity:
    def __init__(self, client: httpx.Client, *, profile: DeviceProfile) -> None:
        self.client = client
        self.profile = profile

    def register(self, *, health_access_token: str, user_id: str, cdid: str) -> str:
        response = safe_http_call(
            "SCSP registration",
            lambda: self.client.post(
                f"{PLAY_URL}/identity/v1/register",
                headers=self._headers(health_access_token, user_id, cdid),
                json={
                    "app": {"version": APP_VERSION},
                    "device": {
                        "osType": "android",
                        "osVersion": self.profile.android_sdk,
                        "platformVersion": self.profile.platform_version,
                        "type": self.profile.device_type,
                        "countryCode": self.profile.country_code,
                        "modelName": self.profile.model_name,
                        "alias": self.profile.alias,
                        "osUserId": self.profile.os_user_id,
                    },
                },
                follow_redirects=False,
            ),
        )
        _validate_response_url(
            response,
            expected_host="play.samsungcloud.com",
            expected_path="/identity/v1/register",
            operation="SCSP registration",
        )
        payload = self._json(response, "SCSP registration")
        registration_id = payload.get("registrationId")
        if not isinstance(registration_id, str) or not registration_id:
            raise SamsungHealthCloudError("SCSP registration response missing registration id")
        return registration_id

    def issue_token(self, *, health_access_token: str, user_id: str, cdid: str) -> CloudToken:
        headers = self._headers(health_access_token, user_id, cdid)
        headers["x-sc-app-version"] = APP_VERSION
        response = safe_http_call(
            "SCSP token",
            lambda: self.client.post(
                f"{PLAY_URL}/identity/v1/tokens",
                headers=headers,
                follow_redirects=False,
            ),
        )
        _validate_response_url(
            response,
            expected_host="play.samsungcloud.com",
            expected_path="/identity/v1/tokens",
            operation="SCSP token",
        )
        payload = self._json(response, "SCSP token")
        try:
            token_type = str(payload["tokenType"])
            access_token = str(payload["accessToken"])
            expires_at = int(payload["expiresAt"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SamsungHealthCloudError("SCSP token response missing expected fields") from exc
        if not token_type or not access_token:
            raise SamsungHealthCloudError("SCSP token response contains an empty token")
        return CloudToken(authorization=f"{token_type} {access_token}", expires_at=expires_at)

    def _headers(self, health_access_token: str, user_id: str, cdid: str) -> dict[str, str]:
        client_tag = getattr(self.profile, "client_tag", "ANDROID")
        return {
            "User-Agent": (
                f"{self.profile.model_name}; {client_tag}; com.sec.android.app.shealth={APP_VERSION}; "
                f"android sdk={self.profile.android_sdk}, sw={self.profile.android_release}; "
                f"core={SCSP_VERSION}"
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-sc-app-id": HEALTH_CLIENT_ID,
            "x-sc-cdid": cdid,
            "x-sc-access-token": health_access_token,
            "x-sc-uid": user_id,
        }

    @staticmethod
    def _json(response: httpx.Response, operation: str) -> dict[str, Any]:
        if getattr(response, "history", None) or response.is_redirect:
            raise SamsungHealthCloudError(f"{operation} redirect not allowed")
        if response.status_code != 200:
            raise SamsungHealthCloudError(f"{operation} failed with HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SamsungHealthCloudError(f"{operation} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SamsungHealthCloudError(f"{operation} returned an invalid payload")
        return payload
