from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from .exceptions import SamsungHealthCloudError
from .models import ManifestInfo

__all__ = ["CatalogStore", "ManifestInfo", "load_bundled_manifests"]


def load_bundled_manifests() -> list[ManifestInfo]:
    try:
        resource = files("samsung_health_cloud.resources").joinpath("manifests.json")
        content = resource.read_text(encoding="utf-8")
        payload = json.loads(content)
        return [ManifestInfo(**entry) for entry in payload.get("manifests", [])]
    except Exception as exc:
        raise SamsungHealthCloudError(
            "unable to load bundled Samsung Health manifest catalog"
        ) from exc


class CatalogStore:
    """Private persisted catalog used by the runtime client with bundled fallback."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, *, fallback_to_bundled: bool = True) -> list[ManifestInfo]:
        if not self.path.exists():
            if fallback_to_bundled:
                return load_bundled_manifests()
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return [ManifestInfo(**entry) for entry in payload["manifests"]]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SamsungHealthCloudError(
                "unable to read Samsung Health manifest catalog"
            ) from exc

    def save(self, manifests: Iterable[ManifestInfo]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {
            "manifests": [
                asdict(item)
                for item in sorted(manifests, key=lambda item: item.manifest_id)
            ]
        }
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)
