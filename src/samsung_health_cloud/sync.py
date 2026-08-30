from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from .auth import SamsungHealthCloudError
from .cache import HealthCache
from .catalog import ManifestInfo


class CacheSynchronizer:
    def __init__(
        self,
        cache: HealthCache,
        data_client,
        *,
        cloud_authorization: str,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.cache = cache
        self.data_client = data_client
        self.cloud_authorization = cloud_authorization
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

    def sync(
        self,
        manifests: Iterable[ManifestInfo],
        *,
        since_ms: int | None,
        until_ms: int | None,
        max_age_ms: int = 0,
        force: bool = False,
    ) -> dict:
        result = {
            "synced_manifests": 0,
            "skipped_fresh": 0,
            "failed_manifests": 0,
            "unavailable_manifests": 0,
            "fetched_records": 0,
            "pruned_records": 0,
            "errors": [],
        }
        now = self.now_ms()
        for manifest in manifests:
            status = self.cache.sync_status(manifest.manifest_id)
            if (
                not force
                and status
                and status["schema_revision"] == manifest.schema_revision
                and status["error"] is None
                and now - status["last_sync_ms"] <= max_age_ms
            ):
                result["skipped_fresh"] += 1
                continue
            try:
                fetched = 0
                batch = []
                seen_ids: set[str] | None = set() if since_ms is None else None
                for envelope in self.data_client.iter_documents(
                    manifest_id=manifest.manifest_id,
                    schema_revision=manifest.schema_revision,
                    cloud_authorization=self.cloud_authorization,
                    page_size=1000,
                    e2ee_state="disabled",
                    start_time=since_ms,
                    end_time=until_ms,
                ):
                    if seen_ids is not None:
                        seen_ids.add(self.cache.document_id(envelope))
                    batch.append(envelope)
                    if len(batch) >= 1000:
                        fetched += self.cache.upsert_documents(
                            manifest.manifest_id, batch
                        )
                        batch.clear()
                fetched += self.cache.upsert_documents(manifest.manifest_id, batch)
                if seen_ids is not None:
                    result["pruned_records"] += self.cache.prune_manifest_except(
                        manifest.manifest_id, seen_ids
                    )
                self.cache.mark_synced(
                    manifest.manifest_id,
                    schema_revision=manifest.schema_revision,
                    synced_at=now,
                    record_count=self.cache.total_records(manifest.manifest_id),
                )
                result["synced_manifests"] += 1
                result["fetched_records"] += fetched
            except SamsungHealthCloudError as exc:
                if "HTTP 404" in str(exc):
                    message = "unavailable: HTTP 404"
                    self.cache.mark_synced(
                        manifest.manifest_id,
                        schema_revision=manifest.schema_revision,
                        synced_at=now,
                        record_count=self.cache.total_records(manifest.manifest_id),
                        error=message,
                    )
                    result["unavailable_manifests"] += 1
                    continue
                message = "SamsungHealthCloudError: sync failed"
                self.cache.mark_synced(
                    manifest.manifest_id,
                    schema_revision=manifest.schema_revision,
                    synced_at=now,
                    record_count=self.cache.total_records(manifest.manifest_id),
                    error=message,
                )
                result["failed_manifests"] += 1
                result["errors"].append(
                    {"manifest_id": manifest.manifest_id, "error": message}
                )
            except Exception as exc:  # noqa: BLE001 - per-manifest isolation; never include request/token details
                message = f"{type(exc).__name__}: sync failed"
                self.cache.mark_synced(
                    manifest.manifest_id,
                    schema_revision=manifest.schema_revision,
                    synced_at=now,
                    record_count=self.cache.total_records(manifest.manifest_id),
                    error=message,
                )
                result["failed_manifests"] += 1
                result["errors"].append(
                    {"manifest_id": manifest.manifest_id, "error": message}
                )
        return result
