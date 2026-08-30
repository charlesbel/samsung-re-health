from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path


class HealthCache:
    """Private SQLite cache of Samsung Health cloud envelopes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    manifest_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    start_time INTEGER,
                    end_time INTEGER,
                    create_time INTEGER,
                    update_time INTEGER,
                    data_json TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    need_to_decrypt INTEGER NOT NULL DEFAULT 0,
                    has_files INTEGER NOT NULL DEFAULT 0,
                    has_download_urls INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (manifest_id, document_id)
                );
                CREATE INDEX IF NOT EXISTS documents_time
                    ON documents(manifest_id, start_time, end_time);
                CREATE INDEX IF NOT EXISTS documents_end_time
                    ON documents(manifest_id, end_time, start_time);
                CREATE INDEX IF NOT EXISTS documents_update
                    ON documents(manifest_id, update_time);
                CREATE TABLE IF NOT EXISTS sync_state (
                    manifest_id TEXT PRIMARY KEY,
                    schema_revision INTEGER NOT NULL,
                    last_sync_ms INTEGER NOT NULL,
                    record_count INTEGER NOT NULL,
                    error TEXT
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(documents)")}
            if "has_files" not in columns:
                db.execute(
                    "ALTER TABLE documents ADD COLUMN has_files INTEGER NOT NULL DEFAULT 0"
                )
                db.execute(
                    "UPDATE documents SET has_files = CASE WHEN json_array_length(json_extract(envelope_json, '$.files')) > 0 THEN 1 ELSE 0 END"
                )
            if "has_download_urls" not in columns:
                db.execute(
                    "ALTER TABLE documents ADD COLUMN has_download_urls INTEGER NOT NULL DEFAULT 0"
                )
                db.execute(
                    "UPDATE documents SET has_download_urls = CASE WHEN json_array_length(json_extract(envelope_json, '$.downloadUrls')) > 0 THEN 1 ELSE 0 END"
                )
        os.chmod(self.path, 0o600)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{self.path}{suffix}")
            if sidecar.exists():
                os.chmod(sidecar, 0o600)

    @staticmethod
    def _document_id(envelope: dict, data_json: str) -> str:
        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
        for key in ("datauuid", "uuid", "id"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        return hashlib.sha256(data_json.encode("utf-8")).hexdigest()

    @classmethod
    def document_id(cls, envelope: dict) -> str:
        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
        data_json = json.dumps(
            data, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        return cls._document_id(envelope, data_json)

    def prune_manifest_except(self, manifest_id: str, keep_ids: Iterable[str]) -> int:
        with self._connect() as db:
            db.execute(
                "CREATE TEMP TABLE IF NOT EXISTS sync_keep_ids(document_id TEXT PRIMARY KEY)"
            )
            db.execute("DELETE FROM sync_keep_ids")
            db.executemany(
                "INSERT OR IGNORE INTO sync_keep_ids(document_id) VALUES (?)",
                ((item,) for item in keep_ids),
            )
            cursor = db.execute(
                "DELETE FROM documents WHERE manifest_id = ? AND document_id NOT IN (SELECT document_id FROM sync_keep_ids)",
                (manifest_id,),
            )
            return cursor.rowcount

    def upsert_documents(self, manifest_id: str, envelopes: Iterable[dict]) -> int:
        rows = []
        for envelope in envelopes:
            data = (
                envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
            )
            data_json = json.dumps(
                data, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            rows.append(
                (
                    manifest_id,
                    self._document_id(envelope, data_json),
                    data.get(
                        "start_time", data.get("day_time", data.get("create_time"))
                    ),
                    data.get(
                        "end_time",
                        data.get(
                            "start_time", data.get("day_time", data.get("create_time"))
                        ),
                    ),
                    data.get("create_time"),
                    data.get("update_time", data.get("create_time")),
                    data_json,
                    json.dumps(
                        envelope,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    int(envelope.get("needToDecrypt") is True),
                    int(
                        isinstance(envelope.get("files"), list)
                        and bool(envelope["files"])
                    ),
                    int(
                        isinstance(envelope.get("downloadUrls"), list)
                        and bool(envelope["downloadUrls"])
                    ),
                )
            )
        if not rows:
            return 0
        with self._connect() as db:
            db.executemany(
                """
                INSERT INTO documents (
                    manifest_id, document_id, start_time, end_time, create_time,
                    update_time, data_json, envelope_json, need_to_decrypt,
                    has_files, has_download_urls
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(manifest_id, document_id) DO UPDATE SET
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    create_time=excluded.create_time,
                    update_time=excluded.update_time,
                    data_json=excluded.data_json,
                    envelope_json=excluded.envelope_json,
                    need_to_decrypt=excluded.need_to_decrypt,
                    has_files=excluded.has_files,
                    has_download_urls=excluded.has_download_urls
                """,
                rows,
            )
        return len(rows)

    def records(self, manifest_id: str, *, since_ms: int, until_ms: int) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT data_json FROM documents
                WHERE manifest_id = ?
                  AND end_time >= ?
                  AND start_time <= ?
                ORDER BY start_time
                """,
                (manifest_id, since_ms, until_ms),
            ).fetchall()
        return [json.loads(row["data_json"]) for row in rows]

    def mark_synced(
        self,
        manifest_id: str,
        *,
        schema_revision: int,
        synced_at: int,
        record_count: int,
        error: str | None = None,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO sync_state(manifest_id, schema_revision, last_sync_ms, record_count, error)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(manifest_id) DO UPDATE SET
                    schema_revision=excluded.schema_revision,
                    last_sync_ms=excluded.last_sync_ms,
                    record_count=excluded.record_count,
                    error=excluded.error
                """,
                (manifest_id, schema_revision, synced_at, record_count, error),
            )

    def sync_status(self, manifest_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT last_sync_ms, schema_revision, record_count, error FROM sync_state WHERE manifest_id = ?",
                (manifest_id,),
            ).fetchone()
        return dict(row) if row else None

    def envelopes(
        self,
        manifest_id: str,
        *,
        since_ms: int,
        until_ms: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT envelope_json FROM documents
                WHERE manifest_id = ? AND end_time >= ? AND start_time <= ?
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
                """,
                (manifest_id, since_ms, until_ms, limit, offset),
            ).fetchall()
        return [json.loads(row["envelope_json"]) for row in rows]

    def manifest_inventory(self, manifest_id: str) -> dict:
        with self._connect() as db:
            summary = db.execute(
                """
                SELECT COUNT(*) AS records,
                       SUM(need_to_decrypt) AS encrypted_records,
                       SUM(has_files) AS records_with_files,
                       SUM(has_download_urls) AS records_with_download_urls,
                       MIN(start_time) AS earliest_ms,
                       MAX(end_time) AS latest_ms
                FROM documents WHERE manifest_id = ?
                """,
                (manifest_id,),
            ).fetchone()
            field_rows = db.execute(
                """
                SELECT DISTINCT fields.key
                FROM documents, json_each(documents.data_json) AS fields
                WHERE manifest_id = ?
                ORDER BY fields.key
                """,
                (manifest_id,),
            ).fetchall()
        return {
            "manifest_id": manifest_id,
            "records": int(summary["records"] or 0),
            "encrypted_records": int(summary["encrypted_records"] or 0),
            "records_with_files": int(summary["records_with_files"] or 0),
            "records_with_download_urls": int(
                summary["records_with_download_urls"] or 0
            ),
            "earliest_ms": summary["earliest_ms"],
            "latest_ms": summary["latest_ms"],
            "fields": [row["key"] for row in field_rows],
        }

    def global_inventory(self) -> dict:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT COUNT(DISTINCT manifest_id) AS manifests_with_records,
                       COUNT(*) AS records,
                       SUM(need_to_decrypt) AS encrypted_records,
                       SUM(has_files) AS records_with_files,
                       SUM(has_download_urls) AS records_with_download_urls
                FROM documents
                """
            ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}  # noqa: SIM118

    def all_sync_status(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT manifest_id, last_sync_ms, schema_revision, record_count, error FROM sync_state ORDER BY manifest_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def total_records(self, manifest_id: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM documents"
        params: tuple = ()
        if manifest_id is not None:
            query += " WHERE manifest_id = ?"
            params = (manifest_id,)
        with self._connect() as db:
            return int(db.execute(query, params).fetchone()[0])
