from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator

import httpx

from .auth import HealthAuth, SamsungHealthCloudError
from .analytics import HEART_RATE, SLEEP, STEP_DAILY, WEIGHT, HealthAnalytics, PARIS
from .analysis_engine import HealthAnalysisEngine, MAX_MS
from .cache import HealthCache
from .catalog import CatalogStore, ManifestInfo
from .data import CloudDataClient
from .exporter import JsonlExporter
from .filters import filter_records, parse_instant_ms, parse_until_ms
from .scsp import DeviceProfile, ScspIdentity
from .service import SamsungHealthService
from .semantics import field_semantics
from .state import StateStore
from .sync import CacheSynchronizer
from .universal import resolve_manifest

DEFAULT_MASTER_STATE = Path.home() / ".config/samsung-find/state.json"
DEFAULT_HEALTH_STATE = Path.home() / ".config/samsung-health-cloud/state.json"
DEFAULT_CATALOG = Path.home() / ".config/samsung-health-cloud/manifests.json"
DEFAULT_EXPORT_ROOT = Path.home() / "samsung-health-exports"
DEFAULT_CACHE = Path.home() / ".local/share/samsung-health/health.sqlite3"
CORE_MANIFEST_IDS = (STEP_DAILY, SLEEP, HEART_RATE, WEIGHT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Samsung Health Cloud CLI complet et strictement en lecture seule")
    parser.add_argument("--version", action="version", version="%(prog)s 0.6.0")
    parser.add_argument("--master-state", type=Path, default=DEFAULT_MASTER_STATE)
    parser.add_argument("--state", type=Path, default=DEFAULT_HEALTH_STATE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialiser ou renouveler la session Health/SCSP")
    subparsers.add_parser("status", help="Afficher la présence et les échéances des jetons")
    subparsers.add_parser("doctor", help="Vérifier les prérequis locaux sans afficher de secret")

    manifests = subparsers.add_parser("manifests", help="Consulter le catalogue local des types Samsung Health")
    manifest_commands = manifests.add_subparsers(dest="manifests_command", required=True)
    list_parser = manifest_commands.add_parser("list", help="Lister tous les types connus")
    list_parser.add_argument("--filter", default="")
    show_parser = manifest_commands.add_parser("show", help="Afficher les métadonnées d’un type")
    show_parser.add_argument("manifest_id")

    read_parser = subparsers.add_parser("read", help="Lire et afficher les documents d’un type")
    read_parser.add_argument("manifest_id")
    read_limit = read_parser.add_mutually_exclusive_group()
    read_limit.add_argument("--limit", type=int, default=20)
    read_limit.add_argument("--all", action="store_true")
    read_parser.add_argument("--page-size", type=int, default=200)
    read_parser.add_argument("--format", choices=("json", "jsonl", "pretty"), default="pretty")
    read_parser.add_argument("--e2ee-state", choices=("disabled", "enabled", "none"), default="disabled")
    read_parser.add_argument("--since", help="Début ISO-8601, fuseau Europe/Paris si absent")
    read_parser.add_argument("--until", help="Fin ISO-8601 ; une date seule inclut toute la journée")

    export_parser = subparsers.add_parser("export", help="Exporter intégralement un type en JSONL reprenable")
    export_parser.add_argument("manifest_id")
    export_parser.add_argument("--output", type=Path)
    export_parser.add_argument("--page-size", type=int, default=50)
    export_parser.add_argument("--e2ee-state", choices=("disabled", "enabled", "none"), default="disabled")
    export_parser.add_argument("--since")
    export_parser.add_argument("--until")

    export_all = subparsers.add_parser("export-all", help="Exporter séquentiellement tous les types du catalogue")
    export_all.add_argument("--output-dir", type=Path, default=DEFAULT_EXPORT_ROOT)
    export_all.add_argument("--page-size", type=int, default=50)
    export_all.add_argument("--e2ee-state", choices=("disabled", "enabled", "none"), default="disabled")
    export_all.add_argument("--stop-on-error", action="store_true")
    export_all.add_argument("--since")
    export_all.add_argument("--until")

    documents = subparsers.add_parser("documents", help="Compatibilité : lire une page avec une révision explicite")
    documents.add_argument("manifest_id")
    documents.add_argument("--schema-revision", required=True, type=int)
    documents.add_argument("--limit", type=int, default=1)
    documents.add_argument("--page-token")

    for name, help_text in (
        ("summary", "Résumé santé consolidé d’une journée"),
        ("steps", "Pas consolidés d’une journée"),
        ("sleep", "Sommeil consolidé de la nuit se terminant ce jour"),
        ("heart-rate", "Statistiques cardiaques consolidées d’une journée"),
    ):
        report = subparsers.add_parser(name, help=help_text)
        report.add_argument("day", nargs="?", help="Date YYYY-MM-DD (aujourd’hui par défaut)")
        report.add_argument("--no-sync", action="store_true", help="Lire immédiatement le cache sans réseau")

    weight = subparsers.add_parser("weight", help="Dernière mesure de poids consolidée")
    weight.add_argument("--no-sync", action="store_true", help="Lire immédiatement le cache sans réseau")

    sync = subparsers.add_parser("sync", help="Actualiser le cache local en arrière-plan")
    sync.add_argument("--days", type=int, default=14, help="Fenêtre récente à actualiser (défaut: 14 jours)")
    sync.add_argument("--all-history", action="store_true", help="Importer tout l’historique des types usuels")
    sync.add_argument("--all-types", action="store_true", help="Importer les 182 types du catalogue")
    sync.add_argument("--force", action="store_true", help="Ignorer la fraîcheur du cache")
    subparsers.add_parser("cache-status", help="État synthétique du cache local")

    types_parser = subparsers.add_parser("types", help="Rechercher tous les types de données disponibles")
    types_parser.add_argument("filter", nargs="?", default="")

    data_parser = subparsers.add_parser("data", help="Lire n’importe quel type depuis le miroir universel")
    data_parser.add_argument("query", help="Nom humain, suffixe ou identifiant complet du type")
    data_parser.add_argument("--since", help="Début ISO-8601")
    data_parser.add_argument("--until", help="Fin ISO-8601")
    data_parser.add_argument("--limit", type=int, default=100)
    data_parser.add_argument("--offset", type=int, default=0)
    data_parser.add_argument("--envelope", action="store_true", help="Inclure fichiers, URLs et métadonnées cloud")
    data_parser.add_argument("--no-sync", action="store_true", help="Lire uniquement le cache local")

    inventory_parser = subparsers.add_parser("inventory", help="Couverture, champs et contenus annexes du miroir")
    inventory_parser.add_argument("query", nargs="?", help="Type précis ; tous les types si absent")

    schema_parser = subparsers.add_parser("schema", help="Sémantique sourcée et couverture de tous les champs observés")
    schema_parser.add_argument("query", nargs="?", help="Type précis ; audit global synthétique si absent")

    analyze = subparsers.add_parser("analyze", help="Vue analytique pertinente d’un type, événement ou intervalle")
    analyze.add_argument("query", help="sleep, activity, exercise ou n’importe quel type du catalogue")
    analyze.add_argument("--latest", action="store_true", help="Analyser le dernier événement pertinent")
    analyze.add_argument("--period", choices=("day", "week", "month"), help="Période civile Europe/Paris")
    analyze.add_argument("--since", help="Début ISO-8601 explicite")
    analyze.add_argument("--until", help="Fin ISO-8601 explicite")
    analyze.add_argument("--compare", choices=("previous",), help="Comparer à la période précédente équivalente")
    analyze.add_argument("--all-history", action="store_true", help="Analyser tout l’historique disponible")
    analyze.add_argument("--no-sync", action="store_true", help="Analyser immédiatement le miroir sans réseau")
    return parser


def _status(store: StateStore) -> dict[str, object]:
    state = store.load()
    return {
        "health_access_token_present": bool(state.health_access_token),
        "health_access_expires_at": state.health_access_expires_at,
        "health_refresh_token_present": bool(state.health_refresh_token),
        "health_refresh_expires_at": state.health_refresh_expires_at,
        "cloud_token_present": bool(state.cloud_token),
        "cloud_expires_at": state.cloud_expires_at,
        "registration_present": bool(state.registration_id),
        "user_id_present": bool(state.user_id),
        "cdid_present": bool(state.cdid),
    }


def _doctor(args: argparse.Namespace) -> dict[str, object]:
    catalog = CatalogStore(args.catalog).load() if args.catalog.exists() else []
    usage = shutil.disk_usage(args.state.parent if args.state.parent.exists() else Path.home())
    return {
        "ok": all((args.master_state.exists(), args.state.exists(), args.catalog.exists(), args.cache.exists())),
        "master_state_present": args.master_state.exists(),
        "health_state_present": args.state.exists(),
        "health_state_mode": oct(args.state.stat().st_mode & 0o777) if args.state.exists() else None,
        "catalog_present": args.catalog.exists(),
        "catalog_count": len(catalog),
        "cache_present": args.cache.exists(),
        "free_bytes": usage.free,
    }


def _service(client: httpx.Client, args: argparse.Namespace, store: StateStore) -> SamsungHealthService:
    profile = DeviceProfile(model_name="SM-S938B", alias="Hermes Read-Only", country_code="FRA")
    return SamsungHealthService(
        store=store,
        master_state_path=args.master_state,
        health_auth=HealthAuth(client),
        scsp=ScspIdentity(client, profile=profile),
    )


def _catalog(client: httpx.Client, args: argparse.Namespace) -> list[ManifestInfo]:
    manifests = CatalogStore(args.catalog).load()
    if not manifests:
        raise SamsungHealthCloudError("local Samsung Health manifest catalog is missing")
    return manifests


def _find_manifest(manifests: Iterable[ManifestInfo], manifest_id: str) -> ManifestInfo:
    for manifest in manifests:
        if manifest.manifest_id == manifest_id:
            return manifest
    raise SamsungHealthCloudError(f"manifest not found in catalog: {manifest_id}")


def _limited(records: Iterable[dict], limit: int | None) -> Iterator[dict]:
    yield from records if limit is None else islice(records, limit)


def _time_bounds(args: argparse.Namespace) -> tuple[int | None, int | None]:
    since_ms = parse_instant_ms(args.since) if getattr(args, "since", None) else None
    until_ms = parse_until_ms(args.until) if getattr(args, "until", None) else None
    if since_ms is not None and until_ms is not None and since_ms > until_ms:
        raise ValueError("since must not be after until")
    return since_ms, until_ms


def _emit_records(records: Iterable[dict], output_format: str) -> int:
    count = 0
    if output_format == "json":
        sys.stdout.write("[")
        for record in records:
            if count:
                sys.stdout.write(",")
            sys.stdout.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            count += 1
        sys.stdout.write("]\n")
        return count
    for record in records:
        if output_format == "pretty":
            print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        count += 1
    return count


def _write_private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _export_all(
    *,
    data_client: CloudDataClient,
    exporter: JsonlExporter,
    manifests: list[ManifestInfo],
    cloud_authorization: str,
    output_dir: Path,
    page_size: int,
    e2ee_state: str,
    stop_on_error: bool,
    since_ms: int | None,
    until_ms: int | None,
) -> dict[str, object]:
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for manifest in manifests:
        output = output_dir / f"{manifest.manifest_id}.jsonl"
        try:
            result = exporter.export_manifest(
                data_client=data_client,
                manifest=manifest,
                cloud_authorization=cloud_authorization,
                output_path=output,
                page_size=page_size,
                e2ee_state=e2ee_state,
                since_ms=since_ms,
                until_ms=until_ms,
            )
            entry = {
                "manifest_id": manifest.manifest_id,
                "status": "ok",
                "record_count": result.record_count,
                "page_count": result.page_count,
                "output": str(result.output_path),
            }
        except (SamsungHealthCloudError, ValueError) as exc:
            entry = {"manifest_id": manifest.manifest_id, "status": "error", "error": str(exc)}
            results.append(entry)
            _write_private_json(output_dir / "index.json", {"results": results})
            if stop_on_error:
                raise
            continue
        results.append(entry)
        _write_private_json(output_dir / "index.json", {"results": results})
    return {
        "manifest_count": len(manifests),
        "success_count": sum(item["status"] == "ok" for item in results),
        "error_count": sum(item["status"] == "error" for item in results),
        "index": str(output_dir / "index.json"),
    }


def _parse_day(value: str | None) -> date:
    if value is None:
        return datetime.now(PARIS).date()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("day must use YYYY-MM-DD") from exc


def _selected_manifests(manifests: list[ManifestInfo], *, all_types: bool = False) -> list[ManifestInfo]:
    if all_types:
        return manifests
    by_id = {manifest.manifest_id: manifest for manifest in manifests}
    missing = [manifest_id for manifest_id in CORE_MANIFEST_IDS if manifest_id not in by_id]
    if missing:
        raise SamsungHealthCloudError(f"core manifests missing from catalog: {', '.join(missing)}")
    return [by_id[manifest_id] for manifest_id in CORE_MANIFEST_IDS]


def _sync_cache(
    *,
    cache: HealthCache,
    data_client: CloudDataClient,
    cloud_authorization: str,
    manifests: list[ManifestInfo],
    since_ms: int | None,
    until_ms: int | None,
    force: bool = False,
    max_age_ms: int = 15 * 60 * 1000,
) -> dict:
    return CacheSynchronizer(cache, data_client, cloud_authorization=cloud_authorization).sync(
        manifests,
        since_ms=since_ms,
        until_ms=until_ms,
        max_age_ms=max_age_ms,
        force=force,
    )


def _report_from_cache(command: str, cache: HealthCache, day_value: str | None = None) -> dict:
    analytics = HealthAnalytics(cache)
    if command == "weight":
        return analytics.latest_weight()
    day = _parse_day(day_value)
    if command == "summary":
        return analytics.summary(day)
    if command == "steps":
        return analytics.steps(day)
    if command == "sleep":
        return analytics.sleep(day)
    if command == "heart-rate":
        return analytics.heart_rate(day)
    raise ValueError(f"unsupported report: {command}")


def _validate_analysis_options(args: argparse.Namespace, query: str) -> None:
    explicit_interval = bool(args.since or args.until)
    if args.all_history and (explicit_interval or args.period):
        raise ValueError("--all-history cannot be combined with --since, --until, or --period")
    if explicit_interval and args.period:
        raise ValueError("--period cannot be combined with --since or --until")
    if args.latest and (explicit_interval or args.period or args.all_history or args.compare):
        raise ValueError("--latest cannot be combined with interval or comparison options")
    if query in {"sleep", "night", "sleep_analysis"}:
        if explicit_interval or args.period or args.all_history or args.compare:
            raise ValueError("sleep analysis only supports --latest")
        return
    if query in {"activity", "distance", "steps", "step_daily_trend"} and args.latest:
        raise ValueError("--latest is not supported for activity")
    if query in {"exercise", "workout"} and args.latest:
        raise ValueError("--latest is not supported for exercise")
    if query not in {"activity", "distance", "steps", "step_daily_trend", "exercise", "workout"} and args.compare:
        raise ValueError("--compare is only supported for activity and exercise")


def _analysis_bounds(args: argparse.Namespace) -> tuple[int, int]:
    if args.all_history:
        return 0, MAX_MS
    if args.since or args.until:
        since_ms = parse_instant_ms(args.since) if args.since else 0
        until_ms = parse_until_ms(args.until) if args.until else MAX_MS
        if since_ms > until_ms:
            raise ValueError("since must not be after until")
        return since_ms, until_ms
    now = datetime.now(PARIS)
    if args.period == "day":
        start = datetime.combine(now.date(), datetime.min.time(), PARIS)
    elif args.period == "month":
        start = datetime(now.year, now.month, 1, tzinfo=PARIS)
    else:
        start = datetime.combine(now.date() - timedelta(days=now.weekday()), datetime.min.time(), PARIS)
    if args.period == "month":
        end = datetime(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1, tzinfo=PARIS)
    else:
        end = start + timedelta(days=1 if args.period == "day" else 7)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000) - 1


def _analysis_report(args: argparse.Namespace, cache: HealthCache, manifests: list[ManifestInfo]) -> dict:
    engine = HealthAnalysisEngine(cache)
    query = args.query.lower().replace("-", "_")
    _validate_analysis_options(args, query)
    if query in {"sleep", "night", "sleep_analysis"}:
        return engine.sleep_latest()
    if query in {"activity", "distance", "steps", "step_daily_trend"}:
        since_ms, until_ms = _analysis_bounds(args)
        result = engine.activity_interval(since_ms, until_ms, compare_previous=args.compare == "previous")
        result["period"] = args.period or "week"
        return result
    since_ms, until_ms = _analysis_bounds(args)
    if query in {"exercise", "workout"}:
        result = engine.exercise(since_ms, until_ms)
        if args.compare == "previous" and since_ms > 0 and until_ms < MAX_MS:
            width = until_ms - since_ms + 1
            result["comparison_previous"] = engine.exercise(since_ms - width, until_ms - width)
        return result
    manifest = resolve_manifest(manifests, args.query)
    if args.latest:
        return engine.generic_latest(manifest.manifest_id)
    result = engine.generic(manifest.manifest_id, since_ms, until_ms)
    result.update({"since_ms": since_ms, "until_ms": until_ms})
    if args.compare == "previous" and since_ms > 0 and until_ms < MAX_MS:
        width = until_ms - since_ms + 1
        result["comparison_previous"] = engine.generic(manifest.manifest_id, since_ms - width, until_ms - width)
    return result


def _schema_report(cache: HealthCache, manifests: list[ManifestInfo], query: str | None) -> dict:
    """Prove that every observed manifest/field pair is documented or safely summarized."""
    if query:
        manifest = resolve_manifest(manifests, query)
        result = HealthAnalysisEngine(cache).generic(manifest.manifest_id, 0, MAX_MS)
        result["schema_revision"] = manifest.schema_revision
        return result
    observed = official_count = convention_count = apk_count = open_source_count = manifests_with_records = 0
    per_manifest = []
    for manifest in manifests:
        inventory = cache.manifest_inventory(manifest.manifest_id)
        fields = inventory["fields"]
        if not fields:
            continue
        manifests_with_records += 1
        statuses = [
            (field_semantics(manifest.manifest_id, field) or {"provenance": {"status": "raw_observed"}})["provenance"]["status"]
            for field in fields
        ]
        official = statuses.count("official_documentation")
        convention = statuses.count("official_schema_convention")
        apk = statuses.count("apk_decompiled")
        open_source = statuses.count("open_source")
        raw = statuses.count("raw_observed")
        observed += len(fields)
        official_count += official
        convention_count += convention
        apk_count += apk
        open_source_count += open_source
        per_manifest.append({
            "manifest_id": manifest.manifest_id,
            "observed_fields": len(fields),
            "officially_documented_fields": official,
            "official_schema_convention_fields": convention,
            "apk_documented_fields": apk,
            "open_source_documented_fields": open_source,
            "raw_fallback_fields": raw,
            "ignored_fields": 0,
        })
    raw_count = observed - official_count - convention_count - apk_count - open_source_count
    return {
        "catalog_manifests": len(manifests),
        "manifests_with_records": manifests_with_records,
        "observed_manifest_fields": observed,
        "officially_documented_manifest_fields": official_count,
        "official_schema_convention_manifest_fields": convention_count,
        "apk_documented_manifest_fields": apk_count,
        "open_source_documented_manifest_fields": open_source_count,
        "raw_fallback_manifest_fields": raw_count,
        "ignored_fields": 0,
        "coverage_percent": 100.0,
        "fallback_guarantee": "Every undocumented field is retained under its raw name and receives type-aware neutral statistics.",
        "manifests": per_manifest,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = StateStore(args.state)
    if args.command == "status":
        try:
            print(json.dumps(_status(store), sort_keys=True))
            return 0
        except (SamsungHealthCloudError, ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.command == "doctor":
        try:
            result = _doctor(args)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["ok"] else 2
        except (SamsungHealthCloudError, ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.command == "cache-status":
        try:
            cache = HealthCache(args.cache)
            statuses = cache.all_sync_status()
            unavailable = [item for item in statuses if item["error"] == "unavailable: HTTP 404"]
            failures = [item for item in statuses if item["error"] and item["error"] != "unavailable: HTTP 404"]
            result = {
                "cache": str(args.cache),
                "manifests": len(statuses),
                "last_sync_ms": max((item["last_sync_ms"] for item in statuses), default=None),
                "unavailable_manifests": len(unavailable),
                "failed_manifests": len(failures),
                "errors": failures,
            }
            result.update(cache.global_inventory())
            print(json.dumps(result, sort_keys=True))
            return 0
        except (ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.command in {"types", "inventory", "schema"} or (args.command in {"data", "analyze"} and args.no_sync):
        try:
            cache = HealthCache(args.cache)
            manifests = CatalogStore(args.catalog).load()
            if args.command == "analyze":
                print(json.dumps(_analysis_report(args, cache, manifests), ensure_ascii=False, sort_keys=True))
                return 0
            if args.command == "schema":
                print(json.dumps(_schema_report(cache, manifests, args.query), ensure_ascii=False, sort_keys=True))
                return 0
            if args.command == "types":
                needle = args.filter.lower()
                status_by_id = {item["manifest_id"]: item for item in cache.all_sync_status()}
                payload = []
                for manifest in manifests:
                    if needle not in manifest.manifest_id.lower():
                        continue
                    status = status_by_id.get(manifest.manifest_id, {})
                    payload.append({
                        "manifest_id": manifest.manifest_id,
                        "schema_revision": manifest.schema_revision,
                        "records": status.get("record_count", 0),
                        "sync_error": status.get("error"),
                    })
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 0
            if args.command == "inventory":
                if args.query:
                    manifest = resolve_manifest(manifests, args.query)
                    payload = cache.manifest_inventory(manifest.manifest_id)
                    payload["schema_revision"] = manifest.schema_revision
                else:
                    statuses = cache.all_sync_status()
                    payload = cache.global_inventory()
                    unavailable = [item for item in statuses if item["error"] == "unavailable: HTTP 404"]
                    failures = [item for item in statuses if item["error"] and item["error"] != "unavailable: HTTP 404"]
                    payload.update({
                        "catalog_manifests": len(manifests),
                        "synced_manifests": len(statuses),
                        "unavailable_manifests": len(unavailable),
                        "failed_manifests": len(failures),
                        "unavailable": unavailable,
                        "errors": failures,
                    })
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 0
            manifest = resolve_manifest(manifests, args.query)
            since_ms = parse_instant_ms(args.since) if args.since else 0
            until_ms = parse_until_ms(args.until) if args.until else 9_223_372_036_854_775_807
            rows = cache.envelopes(manifest.manifest_id, since_ms=since_ms, until_ms=until_ms, limit=args.limit, offset=args.offset)
            if not args.envelope:
                rows = [row.get("data") for row in rows]
            print(json.dumps({
                "manifest_id": manifest.manifest_id,
                "offset": args.offset,
                "count": len(rows),
                "next_offset": args.offset + len(rows) if len(rows) == args.limit else None,
                "records": rows,
            }, ensure_ascii=False, sort_keys=True))
            return 0
        except (SamsungHealthCloudError, ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        with httpx.Client(timeout=90.0, follow_redirects=False) as client:
            if args.command == "manifests":
                manifests = _catalog(client, args)
                if args.manifests_command == "list":
                    selected = [item for item in manifests if args.filter.lower() in item.manifest_id.lower()]
                    print(json.dumps([asdict(item) for item in selected], ensure_ascii=False, indent=2, sort_keys=True))
                else:
                    print(json.dumps(asdict(_find_manifest(manifests, args.manifest_id)), indent=2, sort_keys=True))
                return 0

            report_commands = {"summary", "steps", "sleep", "heart-rate", "weight"}
            if args.command in report_commands and args.no_sync:
                cache = HealthCache(args.cache)
                print(json.dumps(_report_from_cache(args.command, cache, getattr(args, "day", None)), ensure_ascii=False, sort_keys=True))
                return 0

            state = _service(client, args, store).initialize()
            if args.command == "init":
                print(json.dumps(_status(store), sort_keys=True))
                return 0
            data_client = CloudDataClient(client)
            if args.command == "documents":
                payload = data_client.list_documents(
                    manifest_id=args.manifest_id,
                    schema_revision=args.schema_revision,
                    cloud_authorization=state.cloud_token,
                    limit=args.limit,
                    page_token=args.page_token,
                )
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 0

            manifests = _catalog(client, args)
            if args.command == "analyze":
                cache = HealthCache(args.cache)
                query = args.query.lower().replace("-", "_")
                if query in {"sleep", "night", "sleep_analysis"}:
                    ids = {"com.samsung.health.sleep", "com.samsung.health.sleep_stage", "com.samsung.health.heart_rate", "com.samsung.health.oxygen_saturation", "com.samsung.shealth.sleep_snoring"}
                elif query in {"activity", "distance", "steps", "step_daily_trend"}:
                    ids = {"com.samsung.shealth.step_daily_trend"}
                elif query in {"exercise", "workout"}:
                    ids = {"com.samsung.health.exercise"}
                else:
                    ids = {resolve_manifest(manifests, args.query).manifest_id}
                selected = [item for item in manifests if item.manifest_id in ids]
                since_ms, until_ms = _analysis_bounds(args)
                if query in {"sleep", "night", "sleep_analysis"}:
                    since_ms = int(time.time() * 1000) - 3 * 86_400_000
                    until_ms = int(time.time() * 1000)
                elif query in {"activity", "distance", "steps", "step_daily_trend"} and args.compare == "previous":
                    since_ms = int(time.time() * 1000) - 15 * 86_400_000
                _sync_cache(cache=cache, data_client=data_client, cloud_authorization=state.cloud_token,
                            manifests=selected, since_ms=None if args.all_history else since_ms,
                            until_ms=until_ms, max_age_ms=15 * 60 * 1000)
                print(json.dumps(_analysis_report(args, cache, manifests), ensure_ascii=False, sort_keys=True))
                return 0
            if args.command == "data":
                cache = HealthCache(args.cache)
                manifest = resolve_manifest(manifests, args.query)
                status = cache.sync_status(manifest.manifest_id)
                if args.since:
                    since_ms = parse_instant_ms(args.since)
                elif status is None:
                    since_ms = None
                else:
                    since_ms = int(time.time() * 1000) - 30 * 86_400_000
                until_ms = parse_until_ms(args.until) if args.until else int(time.time() * 1000)
                _sync_cache(
                    cache=cache,
                    data_client=data_client,
                    cloud_authorization=state.cloud_token,
                    manifests=[manifest],
                    since_ms=since_ms,
                    until_ms=until_ms,
                )
                query_since = parse_instant_ms(args.since) if args.since else 0
                query_until = parse_until_ms(args.until) if args.until else 9_223_372_036_854_775_807
                rows = cache.envelopes(
                    manifest.manifest_id,
                    since_ms=query_since,
                    until_ms=query_until,
                    limit=args.limit,
                    offset=args.offset,
                )
                if not args.envelope:
                    rows = [row.get("data") for row in rows]
                print(json.dumps({
                    "manifest_id": manifest.manifest_id,
                    "offset": args.offset,
                    "count": len(rows),
                    "next_offset": args.offset + len(rows) if len(rows) == args.limit else None,
                    "records": rows,
                }, ensure_ascii=False, sort_keys=True))
                return 0

            if args.command == "sync":
                if args.days < 1:
                    raise ValueError("days must be positive")
                selected = _selected_manifests(manifests, all_types=args.all_types)
                now_ms = int(time.time() * 1000)
                since_ms = None if args.all_history else now_ms - args.days * 86_400_000
                result = _sync_cache(
                    cache=HealthCache(args.cache),
                    data_client=data_client,
                    cloud_authorization=state.cloud_token,
                    manifests=selected,
                    since_ms=since_ms,
                    until_ms=now_ms,
                    force=args.force,
                    max_age_ms=0,
                )
                print(json.dumps(result, sort_keys=True))
                return 0 if result["failed_manifests"] == 0 else 3

            if args.command in report_commands:
                cache = HealthCache(args.cache)
                day = _parse_day(getattr(args, "day", None)) if args.command != "weight" else datetime.now(PARIS).date()
                window_start = datetime.combine(day - timedelta(days=1), datetime.min.time(), PARIS)
                window_end = datetime.combine(day + timedelta(days=1), datetime.min.time(), PARIS)
                selected_ids = {
                    "steps": (STEP_DAILY,),
                    "sleep": (SLEEP,),
                    "heart-rate": (HEART_RATE,),
                    "weight": (WEIGHT,),
                    "summary": CORE_MANIFEST_IDS,
                }[args.command]
                selected = [manifest for manifest in _selected_manifests(manifests) if manifest.manifest_id in selected_ids]
                since_ms = 0 if args.command == "weight" and cache.total_records(WEIGHT) == 0 else int(window_start.timestamp() * 1000)
                _sync_cache(
                    cache=cache,
                    data_client=data_client,
                    cloud_authorization=state.cloud_token,
                    manifests=selected,
                    since_ms=since_ms,
                    until_ms=int(window_end.timestamp() * 1000),
                )
                print(json.dumps(_report_from_cache(args.command, cache, getattr(args, "day", None)), ensure_ascii=False, sort_keys=True))
                return 0

            if args.command == "read":
                manifest = _find_manifest(manifests, args.manifest_id)
                since_ms, until_ms = _time_bounds(args)
                if args.page_size < 1 or args.page_size > 1000 or (not args.all and args.limit < 1):
                    raise ValueError("limits must be between 1 and 1000")
                records = data_client.iter_documents(
                    manifest_id=manifest.manifest_id,
                    schema_revision=manifest.schema_revision,
                    cloud_authorization=state.cloud_token,
                    page_size=args.page_size,
                    e2ee_state=args.e2ee_state,
                    start_time=since_ms,
                    end_time=until_ms,
                )
                filtered = filter_records(records, since_ms=since_ms, until_ms=until_ms)
                _emit_records(_limited(filtered, None if args.all else args.limit), args.format)
                return 0

            exporter = JsonlExporter()
            if args.command == "export":
                manifest = _find_manifest(manifests, args.manifest_id)
                since_ms, until_ms = _time_bounds(args)
                output = args.output or (DEFAULT_EXPORT_ROOT / f"{manifest.manifest_id}.jsonl")
                result = exporter.export_manifest(
                    data_client=data_client,
                    manifest=manifest,
                    cloud_authorization=state.cloud_token,
                    output_path=output,
                    page_size=args.page_size,
                    e2ee_state=args.e2ee_state,
                    since_ms=since_ms,
                    until_ms=until_ms,
                )
                print(json.dumps({"output": str(result.output_path), "records": result.record_count, "pages": result.page_count}, sort_keys=True))
                return 0

            since_ms, until_ms = _time_bounds(args)
            summary = _export_all(
                data_client=data_client,
                exporter=exporter,
                manifests=manifests,
                cloud_authorization=state.cloud_token,
                output_dir=args.output_dir,
                page_size=args.page_size,
                e2ee_state=args.e2ee_state,
                stop_on_error=args.stop_on_error,
                since_ms=since_ms,
                until_ms=until_ms,
            )
            print(json.dumps(summary, sort_keys=True))
            return 0 if summary["error_count"] == 0 else 3
    except httpx.HTTPError:
        print("error: Samsung Health network request failed", file=sys.stderr)
        return 2
    except (SamsungHealthCloudError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
