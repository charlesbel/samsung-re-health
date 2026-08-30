from __future__ import annotations

import re
from typing import Any

import httpx

from .auth import SamsungHealthCloudError, safe_http_call
from .scsp import APP_VERSION

DATA_URL = "https://api.samsungcloud.com"
_MANIFEST_PATTERN = re.compile(r"com\.samsung\.(?:health|shealth)(?:\.[a-z0-9_]+)+")
_E2EE_HEADERS = {"enabled": "ON", "disabled": "OFF", "none": "NONE"}


class CloudDataClient:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

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
        if (start_time is not None and start_time < 0) or (
            end_time is not None and end_time < 0
        ):
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
        response = safe_http_call(
            "document GET",
            lambda: self.client.get(
                f"{DATA_URL}/data/v3/{manifest_id}/documents",
                params=params,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": f"SM-S938B; HERMES; com.sec.android.app.shealth={APP_VERSION}",
                    "authorization": cloud_authorization,
                    "x-sc-e2ee-state": _E2EE_HEADERS[e2ee_state],
                },
            ),
        )
        if response.status_code != 200:
            raise SamsungHealthCloudError(
                f"document GET failed with HTTP {response.status_code}"
            )
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
        page_size: int = 200,
        start_page_token: str | None = None,
        e2ee_state: str = "disabled",
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        page_token = start_page_token
        seen_tokens: set[str] = {start_page_token} if start_page_token else set()
        while True:
            payload = self.list_documents(
                manifest_id=manifest_id,
                schema_revision=schema_revision,
                cloud_authorization=cloud_authorization,
                limit=page_size,
                page_token=page_token,
                e2ee_state=e2ee_state,
                start_time=start_time,
                end_time=end_time,
            )
            documents = payload.get("documents")
            if not isinstance(documents, list):
                raise SamsungHealthCloudError(
                    "document GET response is missing its documents list"
                )
            has_next = payload.get("hasNext") is True
            next_page_token = payload.get("nextPageToken") if has_next else None
            if has_next and (
                not isinstance(next_page_token, str) or not next_page_token
            ):
                raise SamsungHealthCloudError(
                    "document GET response is missing its next page token"
                )
            if next_page_token is not None and next_page_token in seen_tokens:
                raise SamsungHealthCloudError("document pagination loop detected")
            yield payload
            if not has_next:
                return
            seen_tokens.add(next_page_token)
            page_token = next_page_token

    def iter_documents(
        self,
        *,
        manifest_id: str,
        schema_revision: int,
        cloud_authorization: str,
        page_size: int = 200,
        start_page_token: str | None = None,
        e2ee_state: str = "disabled",
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        for payload in self.iter_pages(
            manifest_id=manifest_id,
            schema_revision=schema_revision,
            cloud_authorization=cloud_authorization,
            page_size=page_size,
            start_page_token=start_page_token,
            e2ee_state=e2ee_state,
            start_time=start_time,
            end_time=end_time,
        ):
            yield from payload["documents"]
