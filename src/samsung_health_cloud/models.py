from __future__ import annotations

import re
from dataclasses import dataclass, field

_MANIFEST_ID_PATTERN = re.compile(r"com\.samsung\.(?:health|shealth)(?:\.[a-z0-9_]+)+")
_COUNTRY_PATTERN = re.compile(r"^[A-Z]{3}$")
_SDK_PATTERN = re.compile(r"^[0-9]{1,3}$")
_VALID_DEVICE_TYPES = {"phone", "tablet", "wearable", "watch", "generic", "desktop"}
_VALID_CLIENT_TAGS = {"ANDROID", "IOS", "TIZEN", "GENERIC"}


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    model_name: str = "SM-GENERIC"
    alias: str = "Samsung Health Cloud Client"
    country_code: str = "USA"
    android_sdk: str = "34"
    android_release: str = "14"
    platform_version: str = "6.0.0"
    device_type: str = "phone"
    os_user_id: str = "0"
    client_tag: str = "ANDROID"

    def __post_init__(self) -> None:
        fields = [
            ("model_name", self.model_name),
            ("alias", self.alias),
            ("country_code", self.country_code),
            ("android_sdk", self.android_sdk),
            ("android_release", self.android_release),
            ("platform_version", self.platform_version),
            ("device_type", self.device_type),
            ("os_user_id", self.os_user_id),
            ("client_tag", self.client_tag),
        ]
        for name, val in fields:
            if not isinstance(val, str) or isinstance(val, bool):
                raise ValueError(f"device profile {name} must be a string")
            if any(ord(c) < 32 or ord(c) == 127 for c in val):
                raise ValueError(f"device profile {name} contains invalid control characters")
            if len(val) < 1 or len(val) > 100:
                raise ValueError(f"device profile {name} length must be between 1 and 100")

        if not _COUNTRY_PATTERN.fullmatch(self.country_code):
            raise ValueError(
                f"invalid country_code '{self.country_code}', must be 3 uppercase letters (ISO 3166-1 alpha-3)"
            )
        if not _SDK_PATTERN.fullmatch(self.android_sdk):
            raise ValueError(f"invalid android_sdk '{self.android_sdk}', must be numeric string")
        if self.device_type.lower() not in _VALID_DEVICE_TYPES:
            raise ValueError(
                f"invalid device_type '{self.device_type}', must be one of: {sorted(_VALID_DEVICE_TYPES)}"
            )
        if self.client_tag.upper() not in _VALID_CLIENT_TAGS:
            raise ValueError(
                f"invalid client_tag '{self.client_tag}', must be one of: {sorted(_VALID_CLIENT_TAGS)}"
            )


@dataclass(frozen=True, slots=True)
class ManifestInfo:
    manifest_id: str
    schema_revision: int
    manifest_version: int
    push_id: str = ""

    def __post_init__(self) -> None:
        if _MANIFEST_ID_PATTERN.fullmatch(self.manifest_id) is None:
            raise ValueError(f"invalid Samsung Health manifest id: {self.manifest_id}")
        if self.schema_revision < 0 or self.manifest_version < 0:
            raise ValueError("manifest revisions must be non-negative")


@dataclass(frozen=True, slots=True)
class SyncSummary:
    total_manifests: int = 0
    synced_manifests: int = 0
    failed_manifests: int = 0
    total_records: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CacheInventory:
    manifests_with_records: int = 0
    records: int = 0
    encrypted_records: int = 0
    records_with_files: int = 0
    records_with_download_urls: int = 0
