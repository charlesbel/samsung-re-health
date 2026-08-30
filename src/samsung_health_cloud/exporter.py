from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth import SamsungHealthCloudError
from .catalog import ManifestInfo
from .filters import filter_records


@dataclass(frozen=True, slots=True)
class ExportResult:
    output_path: Path
    record_count: int
    page_count: int


class JsonlExporter:
    def export_manifest(
        self,
        *,
        data_client,
        manifest: ManifestInfo,
        cloud_authorization: str,
        output_path: Path,
        page_size: int = 200,
        e2ee_state: str = "disabled",
        since_ms: int | None = None,
        until_ms: int | None = None,
    ) -> ExportResult:
        if page_size < 1 or page_size > 1000:
            raise ValueError("page size must be between 1 and 1000")
        output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._locked(output_path):
            return self._export_locked(
                data_client=data_client,
                manifest=manifest,
                cloud_authorization=cloud_authorization,
                output_path=output_path,
                page_size=page_size,
                e2ee_state=e2ee_state,
                since_ms=since_ms,
                until_ms=until_ms,
            )

    def _export_locked(
        self,
        *,
        data_client,
        manifest: ManifestInfo,
        cloud_authorization: str,
        output_path: Path,
        page_size: int,
        e2ee_state: str,
        since_ms: int | None,
        until_ms: int | None,
    ) -> ExportResult:
        page_dir = output_path.with_name(f"{output_path.name}.pages")
        if page_dir.is_symlink():
            raise SamsungHealthCloudError("export page directory must not be a symlink")
        page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(page_dir, 0o700)
        state_path = page_dir / "state.json"
        state = self._load_state(state_path)
        if state:
            self._validate_state(
                state,
                manifest=manifest,
                page_size=page_size,
                e2ee_state=e2ee_state,
                since_ms=since_ms,
                until_ms=until_ms,
            )
        else:
            state = {
                "manifest_id": manifest.manifest_id,
                "schema_revision": manifest.schema_revision,
                "manifest_version": manifest.manifest_version,
                "page_size": page_size,
                "next_page_token": None,
                "page_index": 0,
                "record_count": 0,
                "page_hashes": [],
                "final_sha256": None,
                "complete": False,
                "since_ms": since_ms,
                "until_ms": until_ms,
                "e2ee_state": e2ee_state,
            }
            self._save_json(state_path, state)

        page_index = int(state["page_index"])
        record_count = int(state["record_count"])
        page_hashes = list(state["page_hashes"])
        self._validate_pages(page_dir, page_index, page_hashes)

        if state["complete"] is True:
            if output_path.is_symlink():
                raise SamsungHealthCloudError("export output must not be a symlink")
            final_hash = state.get("final_sha256")
            if not isinstance(final_hash, str) or len(final_hash) != 64:
                raise SamsungHealthCloudError("export checkpoint is missing final integrity data")
            if not output_path.exists() or self._sha256_file(output_path) != final_hash:
                rebuilt_hash = self._assemble(page_dir, output_path, page_index, page_hashes)
                state["final_sha256"] = rebuilt_hash
                self._save_json(state_path, state)
            return ExportResult(output_path, record_count, page_index)

        start_page_token = state.get("next_page_token")
        for payload in data_client.iter_pages(
            manifest_id=manifest.manifest_id,
            schema_revision=manifest.schema_revision,
            cloud_authorization=cloud_authorization,
            page_size=page_size,
            start_page_token=start_page_token if isinstance(start_page_token, str) else None,
            e2ee_state=e2ee_state,
            start_time=since_ms,
            end_time=until_ms,
        ):
            raw_documents = payload.get("documents")
            if not isinstance(raw_documents, list):
                raise SamsungHealthCloudError("export page is missing its documents list")
            documents = list(filter_records(raw_documents, since_ms=since_ms, until_ms=until_ms))
            page_path = page_dir / f"{page_index:08d}.jsonl"
            page_hash = self._save_jsonl(page_path, documents)
            if len(page_hashes) != page_index:
                raise SamsungHealthCloudError("export checkpoint page index is inconsistent")
            page_hashes.append(page_hash)
            record_count += len(documents)
            page_index += 1
            has_next = payload.get("hasNext") is True
            next_page_token = payload.get("nextPageToken") if has_next else None
            if has_next and (not isinstance(next_page_token, str) or not next_page_token):
                raise SamsungHealthCloudError("export page is missing its next page token")
            state.update(
                {
                    "next_page_token": next_page_token,
                    "page_index": page_index,
                    "record_count": record_count,
                    "page_hashes": page_hashes,
                    "complete": not has_next,
                }
            )
            self._save_json(state_path, state)
            if not has_next:
                break

        if state.get("complete") is not True:
            raise SamsungHealthCloudError("export stopped before the final page")
        self._validate_pages(page_dir, page_index, page_hashes)
        state["final_sha256"] = self._assemble(page_dir, output_path, page_index, page_hashes)
        self._save_json(state_path, state)
        return ExportResult(output_path, record_count, page_index)

    @staticmethod
    def _validate_state(
        state: dict[str, Any],
        *,
        manifest: ManifestInfo,
        page_size: int,
        e2ee_state: str,
        since_ms: int | None,
        until_ms: int | None,
    ) -> None:
        identity = (
            state.get("manifest_id") == manifest.manifest_id,
            state.get("schema_revision") == manifest.schema_revision,
            state.get("manifest_version") == manifest.manifest_version,
            state.get("page_size") == page_size,
            state.get("since_ms") == since_ms,
            state.get("until_ms") == until_ms,
            state.get("e2ee_state") == e2ee_state,
        )
        if not all(identity):
            raise SamsungHealthCloudError("export checkpoint does not match the requested export")
        page_index = state.get("page_index")
        record_count = state.get("record_count")
        hashes = state.get("page_hashes")
        if (
            not isinstance(page_index, int)
            or isinstance(page_index, bool)
            or page_index < 0
            or not isinstance(record_count, int)
            or isinstance(record_count, bool)
            or record_count < 0
            or not isinstance(state.get("complete"), bool)
            or not isinstance(hashes, list)
            or len(hashes) != page_index
            or any(not isinstance(item, str) or len(item) != 64 for item in hashes)
        ):
            raise SamsungHealthCloudError("invalid export checkpoint")
        next_token = state.get("next_page_token")
        if next_token is not None and (not isinstance(next_token, str) or not next_token):
            raise SamsungHealthCloudError("invalid export checkpoint")

    @staticmethod
    def _load_state(path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise SamsungHealthCloudError("export checkpoint must not be a symlink")
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SamsungHealthCloudError("unable to read export checkpoint") from exc
        if not isinstance(payload, dict):
            raise SamsungHealthCloudError("invalid export checkpoint")
        return payload

    @staticmethod
    def _save_json(path: Path, payload: dict[str, Any]) -> str:
        return JsonlExporter._atomic_write(
            path,
            (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )

    @staticmethod
    def _save_jsonl(path: Path, documents: list[Any]) -> str:
        content = "".join(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n" for document in documents)
        return JsonlExporter._atomic_write(path, content.encode("utf-8"))

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> str:
        if path.is_symlink():
            raise SamsungHealthCloudError("export file must not be a symlink")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _validate_pages(page_dir: Path, page_count: int, page_hashes: list[str]) -> None:
        expected = {f"{index:08d}.jsonl" for index in range(page_count)}
        actual = {path.name for path in page_dir.glob("*.jsonl")}
        unexpected = actual - expected
        missing = expected - actual
        if unexpected:
            raise SamsungHealthCloudError("unexpected export page found")
        if missing:
            raise SamsungHealthCloudError("export checkpoint is missing a page")
        for index, expected_hash in enumerate(page_hashes):
            page_path = page_dir / f"{index:08d}.jsonl"
            if page_path.is_symlink():
                raise SamsungHealthCloudError("export page must not be a symlink")
            if JsonlExporter._sha256_file(page_path) != expected_hash:
                raise SamsungHealthCloudError("export page integrity check failed")

    @staticmethod
    def _assemble(page_dir: Path, output_path: Path, page_count: int, page_hashes: list[str]) -> str:
        if output_path.is_symlink():
            raise SamsungHealthCloudError("export output must not be a symlink")
        JsonlExporter._validate_pages(page_dir, page_count, page_hashes)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as destination:
                for index in range(page_count):
                    page_path = page_dir / f"{index:08d}.jsonl"
                    with page_path.open("rb") as source:
                        while chunk := source.read(1024 * 1024):
                            destination.write(chunk)
                            digest.update(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, output_path)
            os.chmod(output_path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)
        return digest.hexdigest()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        except OSError as exc:
            raise SamsungHealthCloudError("unable to verify export integrity") from exc
        return digest.hexdigest()

    @staticmethod
    @contextmanager
    def _locked(output_path: Path):
        lock_path = output_path.with_name(f".{output_path.name}.lock")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            raise SamsungHealthCloudError("unable to acquire export lock") from exc
        try:
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
