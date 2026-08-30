from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import platformdirs

from .credentials import resolve_master_state_path
from .exceptions import UsageError
from .models import DeviceProfile

APP_NAME = "samsung-health-cloud"


def _default_state_path() -> Path:
    return Path(platformdirs.user_state_dir(APP_NAME)) / "state.json"


def _default_cache_path() -> Path:
    return Path(platformdirs.user_data_dir(APP_NAME)) / "health.sqlite3"


def _default_catalog_path() -> Path:
    return Path(platformdirs.user_config_dir(APP_NAME)) / "manifests.json"


def _parse_timezone(tz: str | ZoneInfo) -> ZoneInfo:
    if isinstance(tz, ZoneInfo):
        return tz
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise UsageError(f"invalid timezone name: '{tz}'") from exc


@dataclass(frozen=True, slots=True)
class HealthConfig:
    master_state_path: Path = field(default_factory=resolve_master_state_path)
    state_path: Path = field(default_factory=_default_state_path)
    cache_path: Path = field(default_factory=_default_cache_path)
    catalog_path: Path = field(default_factory=_default_catalog_path)
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    device_profile: DeviceProfile = field(default_factory=DeviceProfile)
    timeout: float = 30.0

    def __init__(
        self,
        master_state_path: Path | str | None = None,
        state_path: Path | str | None = None,
        cache_path: Path | str | None = None,
        catalog_path: Path | str | None = None,
        timezone: str | ZoneInfo = "UTC",
        device_profile: DeviceProfile | None = None,
        timeout: float = 30.0,
    ) -> None:
        object.__setattr__(
            self,
            "master_state_path",
            resolve_master_state_path(master_state_path)
            if master_state_path is not None
            else resolve_master_state_path(),
        )
        object.__setattr__(
            self,
            "state_path",
            Path(state_path) if state_path is not None else _default_state_path(),
        )
        object.__setattr__(
            self,
            "cache_path",
            Path(cache_path) if cache_path is not None else _default_cache_path(),
        )
        object.__setattr__(
            self,
            "catalog_path",
            Path(catalog_path) if catalog_path is not None else _default_catalog_path(),
        )
        object.__setattr__(self, "timezone", _parse_timezone(timezone))
        object.__setattr__(
            self,
            "device_profile",
            device_profile if device_profile is not None else DeviceProfile(),
        )
        object.__setattr__(self, "timeout", float(timeout))

    @classmethod
    def from_env(cls) -> HealthConfig:
        master_env = os.environ.get("SAMSUNG_ACCOUNT_MASTER_STATE")
        state_env = os.environ.get("SAMSUNG_HEALTH_STATE")
        cache_env = os.environ.get("SAMSUNG_HEALTH_CACHE") or os.environ.get(
            "SAMSUNG_HEALTH_CACHE_DB"
        )
        catalog_env = os.environ.get("SAMSUNG_HEALTH_CATALOG")
        tz_env = os.environ.get("SAMSUNG_HEALTH_TIMEZONE", "UTC")
        timeout_env = float(os.environ.get("SAMSUNG_HEALTH_TIMEOUT", "30.0"))

        profile_args: dict[str, str] = {}
        if "SAMSUNG_HEALTH_DEVICE_MODEL" in os.environ:
            profile_args["model_name"] = os.environ["SAMSUNG_HEALTH_DEVICE_MODEL"]
        if "SAMSUNG_HEALTH_DEVICE_ALIAS" in os.environ:
            profile_args["alias"] = os.environ["SAMSUNG_HEALTH_DEVICE_ALIAS"]
        if "SAMSUNG_HEALTH_COUNTRY_CODE" in os.environ:
            profile_args["country_code"] = os.environ["SAMSUNG_HEALTH_COUNTRY_CODE"]
        if "SAMSUNG_HEALTH_ANDROID_SDK" in os.environ:
            profile_args["android_sdk"] = os.environ["SAMSUNG_HEALTH_ANDROID_SDK"]
        if "SAMSUNG_HEALTH_ANDROID_RELEASE" in os.environ:
            profile_args["android_release"] = os.environ["SAMSUNG_HEALTH_ANDROID_RELEASE"]
        if "SAMSUNG_HEALTH_PLATFORM_VERSION" in os.environ:
            profile_args["platform_version"] = os.environ["SAMSUNG_HEALTH_PLATFORM_VERSION"]
        if "SAMSUNG_HEALTH_DEVICE_TYPE" in os.environ:
            profile_args["device_type"] = os.environ["SAMSUNG_HEALTH_DEVICE_TYPE"]

        try:
            profile = DeviceProfile(**profile_args)
        except ValueError as exc:
            raise UsageError(f"invalid device profile environment configuration: {exc}") from exc

        return cls(
            master_state_path=master_env,
            state_path=state_env,
            cache_path=cache_env,
            catalog_path=catalog_env,
            timezone=tz_env,
            device_profile=profile,
            timeout=timeout_env,
        )
