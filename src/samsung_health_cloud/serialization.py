from __future__ import annotations

import json
from typing import Any

__all__ = ["envelope", "error_envelope", "format_output", "redact_secrets"]

_SECRET_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "health_access_token",
    "health_refresh_token",
    "cloud_token",
    "userauth_token",
    "persistent_master_token",
    "authorization",
    "downloadurls",
    "download_urls",
}


def redact_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            low = key.lower()
            if low in _SECRET_KEYS:
                result[key] = "<redacted>"
            elif any(
                s in low
                for s in (
                    "token",
                    "authorization",
                    "secret",
                    "password",
                    "private_",
                    "credential",
                )
            ):
                result[key] = (
                    "<redacted>" if isinstance(value, str) and value else value
                )
            else:
                result[key] = redact_secrets(value)
        return result
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_secrets(item) for item in data)
    return data


def envelope(
    data: Any,
    *,
    schema_version: str = "1.0",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": schema_version,
        "data": redact_secrets(data),
        "meta": meta or {},
    }


def error_envelope(
    code: str,
    message: str,
    *,
    schema_version: str = "1.0",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    err_obj: dict[str, Any] = {"code": code, "message": message}
    if details:
        err_obj["details"] = redact_secrets(details)
    return {
        "ok": False,
        "schema_version": schema_version,
        "error": err_obj,
    }


def format_output(payload: dict[str, Any], output_format: str = "json") -> str:
    if output_format == "jsonl":
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
