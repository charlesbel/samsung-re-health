from __future__ import annotations

import json
from typing import Any

__all__ = ["envelope", "error_envelope", "format_output", "redact_raw_records", "redact_secrets"]

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

_SAFE_RECORD_KEYS = {
    # Timestamps
    "start_time",
    "end_time",
    "create_time",
    "update_time",
    "time_offset",
    "day_time",
    "sleep_date",
    "record_time",
    "timestamp",
    # Metrics
    "count",
    "step_count",
    "calorie",
    "distance",
    "speed",
    "duration",
    "mean_heart_rate",
    "min_heart_rate",
    "max_heart_rate",
    "heart_rate",
    "spo2",
    "oxygen_saturation",
    "weight",
    "height",
    "body_fat",
    "muscle_mass",
    "stage",
    "quality",
    "score",
    "exercise_type",
    "custom_type",
    "systolic",
    "diastolic",
    "pulse",
    "glucose",
    "temperature",
    "caffeine_amount",
    "water_amount",
    "stress_level",
    "source_type",
    # Flags
    "needToDecrypt",
}

_FORBIDDEN_RECORD_KEYS = {
    "datauuid",
    "binning_datauuid",
    "deviceuuid",
    "user_id",
    "cdid",
    "registration_id",
    "downloadurls",
    "download_urls",
    "url",
    "uri",
    "path",
    "file_path",
    "local_path",
    "latitude",
    "longitude",
    "altitude",
    "location",
    "gps",
    "device_id",
    "mac_address",
    "bssid",
    "ssid",
    "imei",
    "serial_number",
    "hardware",
    "comment",
    "note",
    "memo",
    "title",
    "description",
    "label",
    "text",
    "files",
    "source_pkg_name",
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
                result[key] = "<redacted>" if isinstance(value, str) and value else value
            else:
                result[key] = redact_secrets(value)
        return result
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_secrets(item) for item in data)
    return data


def redact_raw_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail-closed raw record privacy redaction for MCP opt-in record tool."""
    redacted_list: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        cleaned: dict[str, Any] = {}
        for k, v in record.items():
            k_low = k.lower()
            if k_low in _FORBIDDEN_RECORD_KEYS:
                cleaned[k] = "[REDACTED]"
            elif k in _SAFE_RECORD_KEYS or k_low in _SAFE_RECORD_KEYS:
                if isinstance(v, (int, float, bool)) or v is None:
                    cleaned[k] = v
                elif isinstance(v, str):
                    if any(ord(c) < 32 or ord(c) == 127 for c in v) or len(v) > 200:
                        cleaned[k] = "[REDACTED]"
                    else:
                        cleaned[k] = v
                elif isinstance(v, (dict, list)):
                    cleaned[k] = "[REDACTED]"
                else:
                    cleaned[k] = "[REDACTED]"
            else:
                # Unknown key -> fail closed
                cleaned[k] = "[REDACTED]"
        redacted_list.append(cleaned)
    return redacted_list


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
