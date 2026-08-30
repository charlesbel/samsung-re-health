from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from .auth import SamsungHealthCloudError

_MANIFEST_ID = re.compile(r"com\.samsung\.(?:health|shealth)(?:\.[a-z0-9_]+)+")


@dataclass(frozen=True, slots=True)
class ManifestInfo:
    manifest_id: str
    schema_revision: int
    manifest_version: int
    push_id: str = ""

    def __post_init__(self) -> None:
        if _MANIFEST_ID.fullmatch(self.manifest_id) is None:
            raise ValueError("invalid Samsung Health manifest id")
        if self.schema_revision < 0 or self.manifest_version < 0:
            raise ValueError("manifest revisions must be non-negative")


class CatalogStore:
    """Private persisted catalog used by the runtime client."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[ManifestInfo]:
        if not self.path.exists():
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
