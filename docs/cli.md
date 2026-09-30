# Samsung Health CLI Reference

> **Disclaimer:** `samsung-re-health` is unofficial and reverse-engineered. Its current Health document client downloads records without modifying them; authentication uses separate technical POST requests, local sync writes the mirror, and private APIs can change without notice.

## Installation and Executable

```bash
python -m pip install samsung-re-health
samsung-re-health [GLOBAL_OPTIONS] COMMAND [OPTIONS]
```

The legacy `samsung-health` and `samsung-health-cloud` executables call the same handlers and emit a deprecation warning on stderr. Machine consumers should parse stdout only.

## Output Contract and Exit Codes

The default output is a versioned JSON success or error envelope with `schema_version: "1.0"`. Global `--output` accepts `json`, `jsonl`, or `pretty`; use JSON for automation.

| Code | Meaning |
|---|---|
| `0` | Complete success |
| `2` | Usage or argument-validation error |
| `3` | Authentication required or revoked |
| `4` | Network or remote-protocol error |
| `5` | Local state, permission, or storage error |
| `6` | Partial result; inspect per-manifest failures |

## Global Options

- `--master-state PATH`: neutral Samsung Account master-state override.
- `--state PATH`: Health-derived session-state override.
- `--catalog PATH`: manifest-catalog override.
- `--cache PATH` / `--cache-db PATH`: SQLite mirror override.
- `--timezone IANA_ZONE`: civil date/period timezone; default is UTC unless configured through the environment.
- `--output {json,jsonl,pretty}`: output format.
- Device-profile overrides: `--device-model`, `--device-alias`, `--country-code`, `--android-sdk`, `--android-release`, `--platform-version`, and `--device-type`.
- `--version`: package version.

Explicit SDK/config values take precedence over environment values, which take precedence over portable defaults.

## Setup and Diagnostics

```bash
samsung-re-health install-handler
samsung-re-health auth-start --country us --locale en-US
samsung-re-health auth-complete
samsung-re-health account-status
samsung-re-health init
samsung-re-health status
samsung-re-health doctor
samsung-re-health cache-status
```

- `install-handler` registers the Linux `ms-app://` callback catcher implemented by `samsung_health_cloud.capture_redirect`.
- `auth-start` emits a Samsung Account browser login URL; `--country` defaults to `us` and `--locale` to `en-US`.
- `auth-complete` securely consumes `samsung-account/redirect.uri` and creates the neutral shared `master-state-v1`.
- `account-status` reports only non-secret master-state presence indicators.
- `init` establishes or renews Health OAuth/SCSP derived state from the neutral master state.
- `status` reports presence and expiry metadata, never token values.
- `doctor` checks local paths, permissions, catalog, SQLite, and disk readiness without printing secrets.
- `cache-status` reports local mirror and synchronization metadata.

`doctor`, `cache-status`, `account-status`, and offline local-client operations do not require a network login. Online operations require a master state created by either the Health bootstrap commands above or the equivalent `samsung-re-find` flow.

## Catalog Discovery

```bash
samsung-re-health manifests list [--filter TEXT]
samsung-re-health manifests show MANIFEST_ID
samsung-re-health types [QUERY]
samsung-re-health inventory [QUERY]
samsung-re-health schema [QUERY]
```

- `manifests` exposes the catalog-oriented compatibility interface.
- `types` resolves human terms, suffixes, and manifest identifiers.
- `inventory` reports local record counts, temporal bounds, attachments/E2EE indicators, unavailable manifests, and sync state.
- `schema` reports field presence, provenance, validation, and neutral statistics. Without a query it summarizes global observed-field coverage.

`coverage_percent == 100` means every observed field is surfaced, not that every field is officially documented or every cloud collection is accessible.

The bundled catalog is a baseline, not a live catalog-discovery API. Version 0.7.2 corrects a bounded set of known stale schema revisions from existing private catalogs in memory. Loading preserves the catalog file, manifest versions, routing metadata, unrelated entries, and custom revisions. Future Samsung schema changes still require a verified update; HTTP 400 is not automatically retried with guessed revisions.

## Preferred Analysis Interface

```bash
samsung-re-health analyze sleep --latest
samsung-re-health analyze activity --period week --compare previous
samsung-re-health analyze exercise --since 2026-08-01 --until 2026-08-31
samsung-re-health analyze weight --latest --no-sync
samsung-re-health analyze exercise --all-history --no-sync
```

Selectors are validated:

- `sleep`: latest composite view (`--latest` or no selector).
- `activity` and `exercise`: `--period day|week|month`, explicit `--since`/`--until`, or `--all-history`; `--compare previous` compares an equivalent preceding interval.
- Generic catalog types: `--latest` or one interval selector.
- `--no-sync`: analyze the current local mirror without authentication or network access.

Do not combine incompatible selectors. The selected `--timezone` controls civil day/week/month boundaries and date-only filters.

## Consolidated Views

```bash
samsung-re-health summary [YYYY-MM-DD] [--no-sync]
samsung-re-health steps [YYYY-MM-DD] [--no-sync]
samsung-re-health sleep [YYYY-MM-DD] [--no-sync]
samsung-re-health heart-rate [YYYY-MM-DD] [--no-sync]
samsung-re-health weight [--no-sync]
```

These are convenience views over the same mirror. Prefer `analyze` when provenance, formulas, comparisons, or generic types matter.

## Universal Mirror Data

```bash
samsung-re-health data QUERY [--since ISO] [--until ISO] \
  [--limit N] [--offset N] [--envelope] [--no-sync]
```

The response contains `manifest_id`, `count`, `offset`, `next_offset`, and `records`. Continue at `next_offset` until it is null. `--envelope` can expose attachment metadata, signed URLs, E2EE markers, and unknown keys; use it only for authorized diagnostics. General CLI raw output is not automatically redacted like the gated MCP record tool.

## Synchronization

```bash
samsung-re-health sync [--days N | --all-history] [--all-types] [--force]
```

Synchronization writes to the private local SQLite mirror and checkpoint state. Cloud Health documents are fetched through validated HTTPS GET requests; the current client exposes no Health-record create/update/delete operation. This describes the implemented command surface, not every operation available on Samsung's private services. `--force`, `--all-types`, and `--all-history` can be expensive because the private API may ignore time bounds.

### On-demand refresh and external scheduling

The package has no built-in daemon or scheduler and does not create cron entries or systemd timers. Query commands that support synchronization refresh only their required manifests unless `--no-sync` is used. This is sufficient for on-demand use, but it does not keep the complete mirror current.

Users who need fresh offline coverage can schedule `samsung-re-health sync --all-types --days 14` externally at a low frequency. A separate `samsung-re-health sync --all-types --all-history --force` run can perform an occasional full reconciliation. Keep full-history runs infrequent, avoid overlapping sync processes, and treat the scheduler configuration as private machine administration rather than package state.

Deleting an external scheduled task leaves the SQLite database and existing records intact. Later online analyses can refresh their selected types, while `--no-sync` continues to read whatever is already stored locally.

## Direct Cloud Compatibility Interfaces

```bash
samsung-re-health read MANIFEST_ID [--limit N | --all] [--page-size N] \
  [--format json|jsonl|pretty] [--e2ee-state disabled|enabled|none] \
  [--since ISO] [--until ISO]

samsung-re-health export MANIFEST_ID [--output PATH] [--page-size N] \
  [--e2ee-state disabled|enabled|none] [--since ISO] [--until ISO]

samsung-re-health export-all [--output-dir PATH] [--page-size N] \
  [--e2ee-state disabled|enabled|none] [--stop-on-error] \
  [--since ISO] [--until ISO]

samsung-re-health documents MANIFEST_ID --schema-revision REVISION \
  [--limit N] [--page-token TOKEN]
```

These lower-level surfaces are for diagnostics, migration, and complete exports. Protect exports as sensitive health data. `documents` is a compatibility page interface requiring an explicit schema revision.

## Interpretation and Privacy

- `raw_observed` fields have no approved semantic meaning or unit.
- Sleep `AWAKE` intervals are not counts of conscious awakenings.
- Source records are not automatically distinct nights.
- Efficiency is a value stored in the Samsung document and passed through without local recalculation; derived stage coverage is computed locally. This project does not claim to know Samsung's generating formula.
- `time_window_only` joins prove temporal overlap, not parentage or causality.
- Never disclose credentials, authorization headers, tokens, signed URLs, internal identifiers, exact coordinates, hardware values, or unnecessary raw records.
- Outputs are descriptive, not diagnostic or prescriptive medical advice.
