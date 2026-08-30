from __future__ import annotations

import re
from collections.abc import Iterable

from .auth import SamsungHealthCloudError
from .catalog import ManifestInfo


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def resolve_manifest(manifests: Iterable[ManifestInfo], query: str) -> ManifestInfo:
    choices = list(manifests)
    exact = [item for item in choices if item.manifest_id == query]
    if exact:
        return exact[0]
    normalized = _normalize(query)
    suffix = [item for item in choices if _normalize(item.manifest_id.rsplit(".", 1)[-1]) == normalized]
    if len(suffix) == 1:
        return suffix[0]
    modern_suffix = [item for item in suffix if item.manifest_id.startswith("com.samsung.health.")]
    if len(modern_suffix) == 1:
        return modern_suffix[0]
    matches = [item for item in choices if normalized in _normalize(item.manifest_id)]
    if not matches:
        raise SamsungHealthCloudError(f"health data type not found: {query}")
    if len(matches) > 1:
        names = ", ".join(item.manifest_id for item in matches[:10])
        raise SamsungHealthCloudError(f"ambiguous health data type '{query}': {names}")
    return matches[0]
