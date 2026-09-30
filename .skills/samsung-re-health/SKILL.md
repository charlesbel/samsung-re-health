---
name: samsung-re-health
description: Query and analyze Samsung Health data safely.
version: 0.7.2
author: Charles Bel, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [samsung-health, health-data, privacy, analytics, mcp]
---

# Samsung Health

Use the installed `samsung-re-health` CLI, Python SDK, or stdio MCP server to synchronize account data into a private local mirror and produce descriptive analyses. The current document client reads cloud records without modifying them. This unofficial reverse-engineered project is not affiliated with Samsung and must not be used for diagnosis or treatment.

## When to Use

- Answer descriptive questions about sleep, activity, exercise, heart rate, weight, stress, oxygen saturation, or another mirrored Samsung Health type.
- Inspect available types, temporal coverage, fields, provenance, and cache status.
- Refresh selected data from Samsung Cloud when the user explicitly permits network synchronization.
- Integrate aggregate/local Health tools into an agent over MCP.
- Retrieve bounded raw records only for authorized diagnostics when aggregate analysis is insufficient.

Do not use it for medical claims, emergency assessment, prescriptive advice, unimplemented cloud mutations, continuous surveillance, or disclosure of another person’s records.

## Prerequisites

1. Install with `terminal(command="python -m pip install 'samsung-re-health[mcp]'")`, preferably in an isolated environment or tool installer.
2. Use `samsung-re-health` and `samsung-re-health-mcp`. Legacy `samsung-health*` entry points are compatibility aliases, not the public documentation target.
3. Offline analysis requires a populated local cache. For online use, create the neutral Samsung Account master state with this package's `auth-start`/`auth-complete` commands or reuse one created by another compatible `samsung-re-*` project. Master and Health-derived state remain separate.
4. State, catalog, SQLite cache, exports, and sidecars must stay in private user-owned platform directories. Never inspect or print authentication files.
5. Health records are sensitive personal data. Return the minimum necessary result and never expose tokens, cookies, signed URLs, internal IDs, exact coordinates, device hardware values, unknown free text, or raw envelopes by default.

## How to Run

Prefer `analyze` for user questions and invoke commands through `terminal`:

```text
terminal(command="samsung-re-health doctor")
terminal(command="samsung-re-health cache-status")
terminal(command="samsung-re-health types sleep")
terminal(command="samsung-re-health analyze sleep --latest --no-sync")
terminal(command="samsung-re-health analyze activity --period week --compare previous --no-sync")
terminal(command="samsung-re-health analyze exercise --all-history --no-sync")
terminal(command="samsung-re-health inventory")
terminal(command="samsung-re-health schema sleep")
```

Add the global `--timezone <IANA zone>` before the subcommand when civil dates must follow a particular locality. Use `--output json` for machine processing; do not scrape pretty output.

## Quick Reference

| Need | Command | Network by default? |
|---|---|---|
| Local prerequisites | `doctor` | No |
| Token/cache metadata | `status`, `cache-status` | No |
| Find type names | `types [QUERY]` | No |
| Best descriptive answer | `analyze QUERY SELECTOR` | Yes unless `--no-sync` |
| Daily consolidated view | `summary [YYYY-MM-DD]` | Yes unless `--no-sync` |
| Coverage and fields | `inventory [QUERY]`, `schema [QUERY]` | No |
| Bounded local records | `data QUERY --limit N --no-sync` | No |
| Explicit refresh | `sync [--days N|--all-history] [--all-types]` | Cloud GET + local writes |

Selectors:

- Sleep: `analyze sleep --latest` (or no selector).
- Activity/exercise: `--period day|week|month`, `--since ... --until ...`, `--all-history`, and optional `--compare previous`.
- Generic catalog types: `--latest` or one interval selector.
- `--no-sync` means immediate local-only analysis; use it whenever the user asks for offline behavior or does not authorize a refresh.

## MCP

Configure the stdio executable `samsung-re-health-mcp`; it opens no listener. Six safe tools are enabled by default:

- `samsung_health_status`
- `samsung_health_types`
- `samsung_health_inventory`
- `samsung_health_analyze`
- `samsung_health_summary`
- `samsung_health_cache_status`

Two tools are deliberately absent unless the host opts in:

- `samsung_health_read_records` with `--allow-records`; hard maximum 50 and fail-closed redaction.
- `samsung_health_sync` with `--allow-sync`; performs explicit GET-only cloud synchronization but mutates the local mirror and derived session state, so its MCP annotations are not read-only or idempotent.

Do not enable either globally “just in case.” The general CLI/SDK raw-data APIs are not automatically redacted like the gated MCP tool.

## Procedure

1. **Choose locality and network policy.** Determine the requested timezone, interval, and whether cloud synchronization is authorized. Completion criterion: timezone and network behavior are explicit rather than assumed.
2. **Check readiness.** Run `terminal(command="samsung-re-health doctor")` and `cache-status`. For offline requests, do not initialize credentials or sync. Completion criterion: cache/catalog problems are distinguished from authentication problems.
3. **Resolve the type.** Run `types <query>` when the human term might map to multiple manifests. Do not guess Samsung manifest IDs. Completion criterion: one intended type is selected or ambiguity is reported.
4. **Analyze first.** Translate the question to `analyze` with exactly one compatible selector. Use `--no-sync` for local-only work. Completion criterion: output includes calculations, provenance, field analysis, and coverage sufficient to explain each reported value.
5. **Inspect semantics before wording.** Read `calculations`, `field_analysis`, `coverage`, validation counters, and provenance. A `raw_observed` field has no approved meaning or unit. Completion criterion: every interpreted value has a supported semantic source or is explicitly described as neutral/raw.
6. **Use raw interfaces only when necessary.** `inventory` and `schema` diagnose coverage. `data` supports `--limit`, `--offset`, `--since`, `--until`, `--envelope`, and `--no-sync`; continue from `next_offset` until null. Do not request envelopes or raw records merely to answer an aggregate question.
7. **Minimize disclosure.** Summarize relevant metrics, date range, source/derivation, and limitations. Do not return full records or sensitive unknown fields unless specifically authorized and necessary.
8. **Verify completion.** Confirm the requested interval and coverage, note unavailable/deprecated/E2EE data, and distinguish “no records,” “not synchronized,” “unavailable,” and “sync failed.”

## Interpretation Rules

- `AWAKE` includes brief awake/restless stage intervals; never translate an interval count into “conscious awakenings.”
- A raw sleep `source_record` is not automatically a distinct night or session.
- `reported_efficiency_percent` comes from Samsung account data. `derived_stage_coverage_percent` is a local union-of-valid-stage-intervals calculation; they are not interchangeable.
- Inspect stage validation counts before using stage totals; invalid values, invalid intervals, and overlaps are explicitly tracked.
- Heart rate, oxygen saturation, and snoring joined by `time_window_only` are temporally concomitant, not proven members or causes of a sleep record.
- Activity totals use Samsung’s authoritative all-sources daily record where available. Missing authoritative records remain unknown rather than being reconstructed from arbitrary fields.
- Exercise heart-rate aggregation is duration-weighted when documented as such.
- `coverage_percent == 100` means every observed field is surfaced, not that Samsung documented every field or that every cloud record is retrievable.
- “Complete” means complete for what the current private API returned. Deprecated 404 manifests, E2EE content, files, signed URLs, and inaccessible collections must be reported as limitations.
- Never infer pathology, danger, sleep quality, fitness, recovery, causality, or treatment from descriptive outputs.

## Current Cloud and Privacy Boundary

- The Health document transport implemented in this release uses fixed HTTPS GET endpoints. This is not a claim that Samsung's private backend has no other operations.
- POST operations, where present, are limited to authentication and SCSP identity/session establishment; they do not mutate user health records.
- No Health-data PUT, PATCH, DELETE, upsert, or deregistration operation is exposed.
- Master credentials are consumed transiently for authentication and never copied into Health state or SQLite.
- The mirror may contain complete sensitive records even though it contains no master credential. Protect the database, WAL/SHM files, exports, and backups alike.
- For tests and protocol smokes, use synthetic state and isolated `HOME`/XDG directories; never point tests at real credentials or records.

## Pitfalls

- The API is private and can change without notice.
- Per-manifest HTTP 400 failures can indicate schema-revision drift rather than expired authentication. Version 0.7.2 corrects known stale revisions in memory without rewriting private catalogs. Diagnose future changes using bounded GET probes and validated response status; never print raw payloads, secrets, or records, and never guess new revisions in normal synchronization.
- The server may ignore requested time bounds and return an entire collection; avoid frequent full-history or all-type syncs.
- Date-only `--until` follows the selected civil timezone; set it explicitly when the user’s day boundary matters.
- `--envelope` can include files, URLs, E2EE markers, and unknown future keys; it is a diagnostic surface, not normal response material.
- Empty, unavailable, unsynchronized, and failed manifests are different states.
- Structural presence is not semantic understanding. Never assign meaning from a field name alone.
- Do not run concurrent sync/credential maintenance jobs against the same private state.

## Verification

A workflow is complete only when:

1. the executable and local prerequisites passed `--version`/`doctor` checks;
2. the timezone, interval, and sync policy match the request;
3. the selected type and coverage are known;
4. each reported metric is labeled as direct, derived, or semantically unknown;
5. sleep and time-window joins follow the interpretation rules above;
6. no secret, raw identifier, signed URL, exact coordinate, or unnecessary record escaped;
7. no cloud mutation was attempted and sensitive MCP tools were enabled only by explicit opt-in.
