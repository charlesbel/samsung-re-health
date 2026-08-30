from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import httpx

from .auth import SamsungHealthCloudError, _validate_response_url, safe_http_call
from .models import DeviceProfile
from .scsp import APP_VERSION

__all__ = ["DATA_URL", "CloudDataClient"]

DATA_URL = "https://api.samsungcloud.com"
_MANIFEST_PATTERN = re.compile(r"com\.samsung\.(?:health|shealth)(?:\.[a-z0-9_]+)+")
_E2EE_HEADERS = {"enabled": "ON", "disabled": "OFF", "none": "NONE"}
_ALLOWED_DATA_HOSTS = {"api.samsungcloud.com"}


def _validate_data_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SamsungHealthCloudError("data transport must use HTTPS")
    if not parsed.hostname:
        raise SamsungHealthCloudError("data transport URL missing hostname")
    if parsed.username or parsed.password:
        raise SamsungHealthCloudError("data transport userinfo forbidden")
    if parsed.port is not None and parsed.port != 443:
        raise SamsungHealthCloudError("data transport non-443 port forbidden")
    if parsed.path not in ("", "/"):
        raise SamsungHealthCloudError("data transport base URL path must be root")
    if parsed.query or parsed.fragment:
        raise SamsungHealthCloudError("data transport query/fragment forbidden")
    hostname = parsed.hostname.lower()
    if hostname not in _ALLOWED_DATA_HOSTS:
        raise SamsungHealthCloudError(f"untrusted host for health data transport: '{hostname}'")
    return f"https://{hostname}"


def _validate_endpoint_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SamsungHealthCloudError("data transport must use HTTPS")
    if not parsed.hostname:
        raise SamsungHealthCloudError("data transport URL missing hostname")
    if parsed.username or parsed.password:
        raise SamsungHealthCloudError("data transport userinfo forbidden")
    if parsed.port is not None and parsed.port != 443:
        raise SamsungHealthCloudError("data transport non-443 port forbidden")
    if not parsed.path.startswith("/data/v3/"):
        raise SamsungHealthCloudError("data transport endpoint path must begin with /data/v3/")
    if parsed.query or parsed.fragment:
        raise SamsungHealthCloudError("data transport query/fragment forbidden in base endpoint")
    hostname = parsed.hostname.lower()
    if hostname not in _ALLOWED_DATA_HOSTS:
        raise SamsungHealthCloudError(f"untrusted host for health data transport: '{hostname}'")
    return url


class CloudDataClient:
    """Strictly GET-only client for fetching documents from Samsung Cloud data endpoints."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str = DATA_URL,
        profile: DeviceProfile | None = None,
    ) -> None:
        self.client = client
        self.base_url = _validate_data_base_url(base_url)
        self.profile = profile or DeviceProfile()

    def list_documents(
        self,
        *,
        manifest_id: str,
        schema_revision: int,
        cloud_authorization: str,
        limit: int = 1,
        page_token: str | None = None,
        e2ee_state: str = "disabled",
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> dict[str, Any]:
        if not _MANIFEST_PATTERN.fullmatch(manifest_id):
            raise ValueError("invalid Samsung Health manifest id")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if schema_revision < 0:
            raise ValueError("schema revision must be non-negative")
        if e2ee_state not in _E2EE_HEADERS:
            raise ValueError("invalid E2EE state")
        if (start_time is not None and start_time < 0) or (end_time is not None and end_time < 0):
            raise ValueError("time bounds must be non-negative")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError("start time must not be after end time")
        params: dict[str, str] = {
            "schemaRevision": str(schema_revision),
            "limit": str(limit),
        }
        if page_token:
            params["pageToken"] = page_token
        if start_time is not None:
            params["start_time"] = str(start_time)
        if end_time is not None:
            params["end_time"] = str(end_time)

        target_url = f"{self.base_url}/data/v3/{manifest_id}/documents"
        _validate_endpoint_url(target_url)

        response = safe_http_call(
            "document GET",
            lambda: self.client.get(
                target_url,
                params=params,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": f"{self.profile.model_name}; {self.profile.client_tag}; com.sec.android.app.shealth={APP_VERSION}",
                    "authorization": cloud_authorization,
                    "x-sc-e2ee-state": _E2EE_HEADERS[e2ee_state],
                },
                follow_redirects=False,
            ),
        )
        parsed_base = urlparse(self.base_url)
        expected_host = (parsed_base.hostname or "api.samsungcloud.com").lower()
        _validate_response_url(
            response,
            expected_host=expected_host,
            expected_path=f"/data/v3/{manifest_id}/documents",
            operation="document GET",
            expected_query=str(httpx.QueryParams(params)),
        )
        if getattr(response, "history", None) or response.is_redirect:
            raise SamsungHealthCloudError("document GET redirect not allowed")
        if response.status_code != 200:
            raise SamsungHealthCloudError(f"document GET failed with HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SamsungHealthCloudError("document GET returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SamsungHealthCloudError("document GET returned an invalid payload")
        return payload

    def iter_pages(
        self,
        *,
        manifest_id: str,
        schema_revision: int,
        cloud_authorization: str,
        limit: int = 1000,
        e2ee_state: str = "disabled",
        start_page_token: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        page_token: str | None = start_page_token
        seen_tokens: set[str] = set()
        if page_token:
            seen_tokens.add(page_token)
        first = True
        while page_token or first:
            first = False
            page = self.list_documents(
                manifest_id=manifest_id,
                schema_revision=schema_revision,
                cloud_authorization=cloud_authorization,
                limit=limit,
                page_token=page_token,
                e2ee_state=e2ee_state,
                start_time=start_time,
                end_time=end_time,
            )
            next_token = page.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                yield page
                break
            if next_token == page_token or next_token in seen_tokens:
                raise SamsungHealthCloudError(f"pagination loop: {manifest_id}")
            seen_tokens.add(next_token)
            yield page
            page_token = next_token

    def iter_documents(
        self,
        *,
        manifest_id: str,
        schema_revision: int,
        cloud_authorization: str,
        page_size: int = 1000,
        e2ee_state: str = "disabled",
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        for page in self.iter_pages(
            manifest_id=manifest_id,
            schema_revision=schema_revision,
            cloud_authorization=cloud_authorization,
            limit=page_size,
            e2ee_state=e2ee_state,
            start_time=start_time,
            end_time=end_time,
        ):
            documents = page.get("documents", [])
            if isinstance(documents, list):
                for doc in documents:
                    if isinstance(doc, dict):
                        yield doc
