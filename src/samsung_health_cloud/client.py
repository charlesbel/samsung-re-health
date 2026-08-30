from __future__ import annotations

import shutil
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Self

import httpx

from .analysis_engine import HealthAnalysisEngine, period_bounds
from .analytics import HealthAnalytics
from .auth import HealthAuth
from .cache import HealthCache
from .catalog import CatalogStore
from .config import HealthConfig
from .credentials import load_master_credentials
from .data import CloudDataClient
from .exceptions import SamsungHealthCloudError, UsageError
from .filters import parse_instant_ms, parse_until_ms
from .scsp import ScspIdentity
from .service import SamsungHealthService
from .state import HealthState, StateStore
from .sync import CacheSynchronizer
from .universal import resolve_manifest

__all__ = ["SamsungHealthClient", "SamsungHealthLocalClient"]


class SamsungHealthLocalClient:
    """Offline-only facade for inspecting local mirror, running analytics, and resolving schemas."""

    def __init__(self, config: HealthConfig | None = None) -> None:
        self.config = config or HealthConfig()
        self._cache = HealthCache(self.config.cache_path)
        self._catalog_store = CatalogStore(self.config.catalog_path)
        self._analysis_engine = HealthAnalysisEngine(self._cache, timezone=self.config.timezone)
        self._analytics = HealthAnalytics(self._cache, timezone=self.config.timezone)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    @property
    def cache(self) -> HealthCache:
        return self._cache

    @property
    def catalog_store(self) -> CatalogStore:
        return self._catalog_store

    def doctor(self) -> dict[str, object]:
        manifests = self._catalog_store.load()
        state_dir = self.config.state_path.parent
        usage_dir = state_dir if state_dir.exists() else Path.home()
        usage = shutil.disk_usage(usage_dir)

        master_exists = self.config.master_state_path.exists()
        master_valid = False
        if master_exists:
            try:
                load_master_credentials(self.config.master_state_path)
                master_valid = True
            except Exception:  # noqa: BLE001
                master_valid = False

        state_exists = self.config.state_path.exists()
        cache_exists = self.config.cache_path.exists()
        catalog_exists = self.config.catalog_path.exists() or len(manifests) > 0

        return {
            "ok": bool(cache_exists or catalog_exists),
            "master_state_path": str(self.config.master_state_path),
            "master_state_present": master_exists,
            "master_state_valid": master_valid,
            "health_state_path": str(self.config.state_path),
            "health_state_present": state_exists,
            "catalog_path": str(self.config.catalog_path),
            "catalog_present": catalog_exists,
            "catalog_count": len(manifests),
            "cache_db": str(self.config.cache_path),
            "cache_present": cache_exists,
            "free_bytes": usage.free,
            "timezone": str(self.config.timezone),
        }

    def types(self, query: str | None = None) -> list[dict[str, object]]:
        manifests = self._catalog_store.load()
        if not query:
            return [
                {
                    "manifest_id": item.manifest_id,
                    "schema_revision": item.schema_revision,
                    "manifest_version": item.manifest_version,
                }
                for item in sorted(manifests, key=lambda m: m.manifest_id)
            ]
        try:
            resolved = resolve_manifest(manifests, query)
            return [
                {
                    "manifest_id": resolved.manifest_id,
                    "schema_revision": resolved.schema_revision,
                    "manifest_version": resolved.manifest_version,
                }
            ]
        except SamsungHealthCloudError:
            # Fallback search substring match
            low = query.lower()
            matches = [m for m in manifests if low in m.manifest_id.lower()]
            return [
                {
                    "manifest_id": item.manifest_id,
                    "schema_revision": item.schema_revision,
                    "manifest_version": item.manifest_version,
                }
                for item in sorted(matches, key=lambda m: m.manifest_id)
            ]

    def inventory(self, manifest_id: str | None = None) -> dict[str, object]:
        if manifest_id:
            manifests = self._catalog_store.load()
            resolved = resolve_manifest(manifests, manifest_id)
            return self._cache.inventory(resolved.manifest_id)
        return self._cache.global_inventory()

    def cache_status(self) -> dict[str, object]:
        summary = self._cache.global_inventory()
        sync_states = self._cache.all_sync_status()
        return {
            "records": summary.get("records", 0),
            "manifests_with_records": summary.get("manifests_with_records", 0),
            "encrypted_records": summary.get("encrypted_records", 0),
            "records_with_files": summary.get("records_with_files", 0),
            "records_with_download_urls": summary.get("records_with_download_urls", 0),
            "sync_states_count": len(sync_states),
            "sync_states": sync_states,
        }

    def summary(self, day: date | str | None = None) -> dict[str, object]:
        if day is None:
            target_day = datetime.now(tz=self.config.timezone).date()
        elif isinstance(day, str):
            target_day = date.fromisoformat(day)
        else:
            target_day = day
        return self._analytics.summary(target_day)

    def analyze(
        self,
        health_type: str,
        *,
        period: str | None = None,
        latest: bool = False,
        since: str | None = None,
        until: str | None = None,
        all_history: bool = False,
        compare: str | None = None,
    ) -> dict[str, object]:
        if compare is not None and compare != "previous":
            raise UsageError(
                f"unsupported compare value: {compare!r}, only \x27previous\x27 is supported"
            )
        if period is not None and period not in ("day", "week", "month"):
            raise UsageError(f"unsupported period: {period!r}, must be one of: day, week, month")

        # Validate option exclusivity
        active_selectors = sum(
            (bool(latest), bool(period), bool(since or until), bool(all_history))
        )
        if active_selectors > 1:
            raise UsageError(
                "options --latest, --period, --since/--until, and --all-history are mutually exclusive"
            )

        manifests = self._catalog_store.load()
        norm_type = health_type.lower().replace("-", "_")

        tz_str = str(self.config.timezone)
        since_ms = parse_instant_ms(since, timezone=tz_str) if since else None
        until_ms = parse_until_ms(until, timezone=tz_str) if until else None

        if since_ms is not None and until_ms is not None and since_ms > until_ms:
            raise UsageError("since timestamp must not be after until timestamp")

        today = datetime.now(tz=self.config.timezone).date()

        if norm_type in ("sleep", "com.samsung.health.sleep"):
            if period or since or until or all_history or compare:
                raise UsageError(
                    "sleep analysis only supports --latest or default (no range selectors)"
                )
            return self._analysis_engine.sleep_latest()

        if norm_type in ("activity", "steps", "com.samsung.shealth.step_daily_trend"):
            if latest:
                raise UsageError("activity analysis does not support --latest")
            if all_history:
                return self._analysis_engine.activity_interval(
                    0,
                    9_223_372_036_854_775_807,
                    compare_previous=(compare == "previous"),
                )
            if since or until:
                return self._analysis_engine.activity_interval(
                    since_ms or 0,
                    until_ms or 9_223_372_036_854_775_807,
                    compare_previous=(compare == "previous"),
                )
            sel_period = period or "week"
            s, u = period_bounds(sel_period, today, tz=self.config.timezone)
            return self._analysis_engine.activity_interval(
                s, u, compare_previous=(compare == "previous")
            )
        if norm_type in ("exercise", "com.samsung.health.exercise"):
            if latest:
                raise UsageError("exercise analysis does not support --latest")
            if all_history:
                return self._analysis_engine.exercise(
                    since_ms=0, until_ms=9_223_372_036_854_775_807
                )
            if since or until:
                return self._analysis_engine.exercise(
                    since_ms=since_ms or 0,
                    until_ms=until_ms or 9_223_372_036_854_775_807,
                )
            sel_period = period or "week"
            s, u = period_bounds(sel_period, today, tz=self.config.timezone)
            res = self._analysis_engine.exercise(since_ms=s, until_ms=u)
            if compare == "previous":
                prev_s, prev_u = period_bounds(
                    sel_period, today, offset=-1, tz=self.config.timezone
                )
                prev_res = self._analysis_engine.exercise(since_ms=prev_s, until_ms=prev_u)
                res["comparison"] = {"previous_period": prev_res}
            return res

        # Generic manifest analysis
        resolved = resolve_manifest(manifests, health_type)
        if compare:
            raise UsageError(f"compare is not supported for generic type '{health_type}'")
        if latest:
            return self._analysis_engine.generic_latest(resolved.manifest_id)
        if all_history:
            return self._analysis_engine.generic(resolved.manifest_id, 0, 9_223_372_036_854_775_807)
        if since or until:
            return self._analysis_engine.generic(
                resolved.manifest_id,
                since_ms or 0,
                until_ms or 9_223_372_036_854_775_807,
            )
        sel_period = period or "week"
        s, u = period_bounds(sel_period, today, tz=self.config.timezone)
        return self._analysis_engine.generic(resolved.manifest_id, s, u)

    def read_data(
        self,
        manifest_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
        offset: int = 0,
        envelope: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 10000:
            raise UsageError("limit must be an integer between 1 and 10000")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise UsageError("offset must be a non-negative integer")

        manifests = self._catalog_store.load()
        resolved = resolve_manifest(manifests, manifest_id)

        tz_str = str(self.config.timezone)
        since_ms = parse_instant_ms(since, timezone=tz_str) if since else None
        until_ms = parse_until_ms(until, timezone=tz_str) if until else None

        if since_ms is not None and until_ms is not None and since_ms > until_ms:
            raise UsageError("since timestamp must not be after until timestamp")

        since_val = since_ms or 0
        until_val = until_ms if until_ms is not None else 9_223_372_036_854_775_807
        if envelope:
            return self._cache.envelopes(
                resolved.manifest_id,
                since_ms=since_val,
                until_ms=until_val,
                limit=limit,
                offset=offset,
            )
        rows = self._cache.records(
            resolved.manifest_id,
            since_ms=since_val,
            until_ms=until_val,
        )
        return rows[offset : offset + limit] if limit is not None else rows[offset:]


class SamsungHealthClient(SamsungHealthLocalClient):
    """Online facade supporting authentication, cloud synchronization, and local mirror analytics."""

    def __init__(
        self,
        config: HealthConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(config)
        self._custom_http = http_client is not None
        self._http_client = http_client or httpx.Client(
            timeout=self.config.timeout, follow_redirects=False
        )
        self._store = StateStore(self.config.state_path)
        self._health_auth = HealthAuth(self._http_client)
        self._scsp = ScspIdentity(self._http_client, profile=self.config.device_profile)
        self._service = SamsungHealthService(
            store=self._store,
            master_state_path=self.config.master_state_path,
            health_auth=self._health_auth,
            scsp=self._scsp,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if not self._custom_http:
            self._http_client.close()

    def initialize_session(self) -> HealthState:
        return self._service.initialize()

    def status(self) -> dict[str, object]:
        state = self._store.load()
        now = int(time.time())
        return {
            "health_access_token_present": bool(state.health_access_token),
            "health_access_expires_at": state.health_access_expires_at,
            "health_access_expired": bool(
                state.health_access_expires_at and state.health_access_expires_at <= now
            ),
            "health_refresh_token_present": bool(state.health_refresh_token),
            "health_refresh_expires_at": state.health_refresh_expires_at,
            "health_refresh_expired": bool(
                state.health_refresh_expires_at and state.health_refresh_expires_at <= now
            ),
            "cloud_token_present": bool(state.cloud_token),
            "cloud_expires_at": state.cloud_expires_at,
            "cloud_token_expired": bool(state.cloud_expires_at and state.cloud_expires_at <= now),
            "user_id_present": bool(state.user_id),
            "cdid_present": bool(state.cdid),
            "registration_id_present": bool(state.registration_id),
        }

    def sync(
        self,
        manifest_id: str | None = None,
        *,
        days: int = 14,
        all_history: bool = False,
        all_types: bool = False,
        force: bool = False,
    ) -> dict[str, object]:
        if manifest_id and all_types:
            raise UsageError("cannot combine specific manifest_id with all_types=True")
        if all_history:
            if days != 14:
                raise UsageError("cannot combine explicit days with all_history=True")
        else:
            if not isinstance(days, int) or isinstance(days, bool) or days < 1 or days > 3650:
                raise UsageError("days must be an integer between 1 and 3650")

        state = self._service.initialize()
        manifests = self._catalog_store.load()
        if not manifests:
            raise SamsungHealthCloudError("manifest catalog is empty; unable to sync")

        if manifest_id:
            resolved = resolve_manifest(manifests, manifest_id)
            target_manifests = [resolved]
        elif all_types:
            target_manifests = manifests
        else:
            core_ids = {
                "com.samsung.health.sleep",
                "com.samsung.health.sleep_stage",
                "com.samsung.health.heart_rate",
                "com.samsung.health.oxygen_saturation",
                "com.samsung.shealth.step_daily_trend",
                "com.samsung.health.exercise",
                "com.samsung.health.weight",
            }
            target_manifests = [m for m in manifests if m.manifest_id in core_ids] or manifests

        data_client = CloudDataClient(self._http_client, profile=self.config.device_profile)
        syncer = CacheSynchronizer(self._cache, data_client, cloud_authorization=state.cloud_token)
        now_ms = int(time.time() * 1000)
        since_ms = 0 if all_history else max(0, now_ms - days * 86_400_000)

        return syncer.sync(
            target_manifests,
            since_ms=since_ms,
            until_ms=None,
            force=force,
        )
