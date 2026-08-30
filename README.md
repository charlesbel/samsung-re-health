# samsung-re-health

[![CI](https://github.com/charlesbel/samsung-re-health/actions/workflows/ci.yml/badge.svg)](https://github.com/charlesbel/samsung-re-health/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/samsung-re-health.svg)](https://pypi.org/project/samsung-re-health/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> **Disclaimer**: This project is unofficial, reverse-engineered, and not affiliated with, endorsed by, or supported by Samsung Electronics Co., Ltd. Samsung Health and Galaxy are trademarks of Samsung Electronics Co., Ltd.

**`samsung-re-health`** is an open-source, strictly read-only Python SDK, typed JSON CLI, and Model Context Protocol (MCP) server for inspecting, synchronizing, querying, and analyzing personal Samsung Health data directly from Samsung Cloud without running an Android emulator or APK.

> **Strict Read-Only Boundary**: All health document synchronization strictly uses HTTPS `GET` requests against validated `*.samsungcloud.com` endpoints. The library possesses no capabilities to create, update, overwrite, or delete health records on Samsung Cloud.

---

## Companion Ecosystem: Samsung Find & Master State

This project can analyze an existing local mirror without network credentials. Online initialization and synchronization use the neutral Master State v1 created by [**`samsung-re-find`**](https://github.com/charlesbel/samsung-re-find); Health never creates or modifies that master state.

Authentication follows the neutral **Master State v1** contract:
- Master credentials are discovered through the platform user configuration directory under `samsung-account/master.json` (for example `~/.config/samsung-account/master.json` on typical Linux systems).
- If no neutral master file exists, the client can read the supported legacy Find state non-destructively and emits a migration warning.
- Health-derived OAuth/SCSP tokens and the SQLite mirror are stored separately from the master state.
- **Strictly Read-Only Health Transport**: health document fetching uses validated HTTPS `GET` requests. Authentication and SCSP session establishment use narrow fixed endpoints but cannot create, update, or delete Health records.

Persistent Health paths retain the compatibility application ID `samsung-health-cloud` so upgrading does not orphan existing mirrors. `platformdirs` chooses OS-specific roots for:

- state: `samsung-health-cloud/state.json` (`SAMSUNG_HEALTH_STATE`);
- SQLite mirror: `samsung-health-cloud/health.sqlite3` (`SAMSUNG_HEALTH_CACHE`, with legacy `SAMSUNG_HEALTH_CACHE_DB` alias);
- manifest catalog: `samsung-health-cloud/manifests.json` (`SAMSUNG_HEALTH_CATALOG`).

The master may be overridden with `SAMSUNG_ACCOUNT_MASTER_STATE`; timezone and timeout use `SAMSUNG_HEALTH_TIMEZONE` and `SAMSUNG_HEALTH_TIMEOUT`. CLI flags and explicit SDK arguments take precedence over environment variables.

---

## Features

- **Typed Python SDK**: High-level `SamsungHealthClient` (online sync + read) and `SamsungHealthLocalClient` (offline mirror analytics) via `import samsung_health_cloud`.
- **Consolidated Analytics**: Built-in aggregations for daily activity (`step_daily_trend`), sleep stages, continuous heart rate, workouts, body weight, oxygen saturation, and stress.
- **Provenance & Formula Tracking**: Analytical outputs publish formula/kind metadata and documented caveats where available; raw-field semantic provenance is tracked separately from structural coverage.
- **Bundled Baseline Catalog**: Out-of-the-box support for standard Samsung Health data types even in pristine environments without an initial network sync.
- **Model Context Protocol (MCP) Server**: Privacy-preserving stdio MCP server (`samsung-re-health-mcp`, server name `samsung-re-health`) with bounded record retrieval and secret redaction.
- **Unified CLI (`samsung-re-health`)**: Structured versioned JSON output with standardized POSIX exit codes (`0`, `2`, `3`, `4`, `5`, `6`). Legacy aliases `samsung-health` and `samsung-health-cloud` are preserved for backward compatibility.

---

## Quick Start

### Installation

Python 3.11 or newer is required. Install into a virtual environment or isolated application environment. CI tests Python 3.11–3.13 on Linux and Python 3.12 on macOS and Windows. Online first-login bootstrap is performed by the companion Find project; Health analysis itself remains portable once the neutral master state and/or local mirror are available:

```bash
# SDK and JSON CLI
python -m pip install samsung-re-health

# SDK, CLI, and MCP stdio server
python -m pip install 'samsung-re-health[mcp]'
```

The distribution name is `samsung-re-health`; the Python import remains `samsung_health_cloud`. Verify installation without credentials or network access:

```bash
samsung-re-health --version
samsung-re-health --help
samsung-re-health-mcp --help
```

For development, clone the repository and install `python -m pip install -e '.[dev,mcp]'`. The repository and source distribution include the portable `.skills/samsung-re-health` agent skill; installing the wheel never modifies an agent profile automatically.

### Authentication for Online Sync

Online synchronization requires a Master State v1 from `samsung-re-find`:

```bash
python -m pip install samsung-re-find
samsung-re-find status
# If no master exists, follow samsung-re-find auth-start/auth-complete.
samsung-re-health init
samsung-re-health status
```

Use Samsung’s browser page for passwords and second factors. Never paste credentials, callback URIs, tokens, or state files into commands, chat, or issues. Local-only analysis of an existing mirror does not require `init`.

### CLI Quick Start

```bash
# Verify environment, local catalog, SQLite mirror, and disk space
samsung-re-health doctor

# Check token presence and expiration timestamps (never logs secrets)
samsung-re-health status

# Synchronize recent health data (defaults to last 14 days)
samsung-re-health sync --days 14

# View multi-metric daily summary
samsung-re-health summary 2026-08-30

# Inspect specific daily metrics
samsung-re-health steps
samsung-re-health sleep
samsung-re-health heart-rate
samsung-re-health weight

# Advanced multi-period analytics
samsung-re-health analyze activity --period week --compare previous
samsung-re-health analyze sleep --latest
samsung-re-health analyze exercise --period month
```

> **Compatibility Note**: Legacy commands `samsung-health` and `samsung-health-cloud` continue to function as aliases with a deprecation notice emitted to stderr.

---

## Python SDK Reference

The Python package import name is `samsung_health_cloud`:

```python
from samsung_health_cloud import SamsungHealthClient, SamsungHealthLocalClient, HealthConfig

config = HealthConfig(timezone="UTC")

# 1. Offline Local Client (queries local SQLite mirror without network)
with SamsungHealthLocalClient(config=config) as local:
    summary = local.summary(day="2026-08-30")
    sleep_analysis = local.analyze("sleep", latest=True)
    manifests = local.types()

# 2. Online Client (auto-refreshes tokens and syncs cloud documents)
with SamsungHealthClient(config=config) as client:
    sync_result = client.sync(days=7)
    status_info = client.status()
```

For complete SDK guides and API contracts, see [`docs/sdk.md`](docs/sdk.md).

---

## Model Context Protocol (MCP) Server

The package includes a stdio-based MCP server providing bounded, privacy-preserving tools for AI assistants:

```bash
samsung-re-health-mcp
```

*(Legacy alias `samsung-health-mcp` is also supported)*

### Registered Tools

The first six tools are available by default and operate on local metadata or aggregate analyses. Raw records and network synchronization are absent unless the MCP host explicitly opts in at startup.

| Tool Name | Availability | Scope | Description |
|---|---|---|---|
| `samsung_health_status` | Default | Metadata | Safe token-expiration status without secrets |
| `samsung_health_types` | Default | Metadata | List supported health manifests and schema revisions |
| `samsung_health_inventory` | Default | Local cache | Record counts and temporal bounds per manifest |
| `samsung_health_analyze` | Default | Analytics | Structured analytics with formulas and provenance |
| `samsung_health_summary` | Default | Analytics | Multi-metric daily summary |
| `samsung_health_cache_status` | Default | Mirror status | SQLite synchronization metadata and error counts |
| `samsung_health_read_records` | `--allow-records` | Sensitive raw data | Values above the 50-record maximum are rejected; output is fail-closed redacted |
| `samsung_health_sync` | `--allow-sync` | Network GET + local writes | Synchronize Health documents into the local mirror; MCP annotations mark it non-read-only and non-idempotent because it updates SQLite/checkpoints |

```bash
# Default six-tool server
samsung-re-health-mcp

# Deliberate opt-ins; do not enable globally without need
samsung-re-health-mcp --allow-records
samsung-re-health-mcp --allow-sync
```

General CLI/SDK raw-data methods are not automatically redacted like the gated MCP record tool. For complete schemas and configuration examples, see [`docs/mcp.md`](docs/mcp.md).

---

## CLI Reference & Exit Codes

The `samsung-re-health` CLI outputs versioned JSON envelopes (`{"ok": true, "schema_version": "1.0", "data": ...}`) by default.

### Standardized Exit Codes
- `0`: Complete success
- `2`: Usage / argument validation error
- `3`: Authentication required or token revoked
- `4`: Remote network or protocol error
- `5`: Local filesystem state / permissions error (`0600` required)
- `6`: Partial result (e.g. some manifests failed sync, reported in payload)

For full CLI options and schema definitions, see [`docs/cli.md`](docs/cli.md).

---

## Documentation Index

- [Architecture & ADR 0001](docs/adr/0001-project-naming.md): Ecosystem naming taxonomy and `samsung-re-{domain}` conventions.
- [Authentication Architecture](docs/authentication.md): Samsung OAuth token exchange, SCSP registration, and Master State v1.
- [Privacy Policy & Safety](docs/privacy.md): Strict read-only boundaries, secret redaction, and local isolation.
- [Research Provenance](docs/research-provenance.md): Methodologies, evidence tiers, and verification limits.
- [Migration Guide](docs/migration-0.7.md): Migrating from legacy setups to `samsung-re-health` 0.7.0.
- [Release Process](docs/release.md): Verification gates, Trusted Publishing, tag sequence, and post-release checks.
- [Python SDK Guide](docs/sdk.md): Facades, data models, and error hierarchy.
- [CLI Reference](docs/cli.md): Commands, arguments, envelopes, and exit codes.
- [MCP Reference](docs/mcp.md): Stdio server tools, bounding rules, and configuration.

---

## Interpretation & Known Limitations

- `coverage_percent == 100` means every observed field is surfaced; it does not mean Samsung documents every field or that every cloud collection is accessible.
- Fields marked `raw_observed` have no approved semantic meaning or unit. The client reports neutral statistics instead of inferring meaning from names.
- Sleep `AWAKE` intervals are not counts of conscious awakenings, and source records are not automatically distinct nights.
- `reported_efficiency_percent` is account data; `derived_stage_coverage_percent` is a local interval-union calculation. They are not interchangeable.
- Heart rate, oxygen saturation, and snoring joined by `time_window_only` are temporally concomitant, not proven parent records or causes.
- Deprecated 404 manifests, E2EE documents, files, signed URLs, and schema changes can limit readable coverage.
- The private API may ignore requested time bounds and return a complete collection; avoid unnecessary frequent all-type/full-history synchronization.
- Outputs are descriptive and must not be treated as diagnosis, medical advice, pathology, recovery, fitness, or causality.

---

## Privacy & Ethical Research

This project is built strictly for personal data sovereignty, transparency, and research.
- **No Private Data**: This repository contains strictly synthetic fixtures, non-personal baseline catalogs, and neutral statistical models.
- **No Live Network Calls in Tests**: All unit, contract, and integration tests run entirely against local mock transports or synthetic SQLite databases.
- **No Write Operations**: Health data transport endpoints are strictly verified to accept only `GET` operations.

---

## License

This project is licensed under the [MIT License](LICENSE).
