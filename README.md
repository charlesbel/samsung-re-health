# Samsung Health Cloud

[![CI](https://github.com/charlesbel/samsung-health-cloud/actions/workflows/ci.yml/badge.svg)](https://github.com/charlesbel/samsung-health-cloud/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Samsung Health Cloud** (`samsung-health-cloud`) is an open-source, strictly read-only Python library, CLI, and MCP stdio server for inspecting, synchronizing, querying, and analyzing personal Samsung Health data directly from Samsung Cloud without running an Android emulator or APK.

---

## Companion Ecosystem: Samsung Find & Master State

This project works independently or as a companion to [**`samsung-find`**](https://github.com/charlesbel/samsung-find).

Authentication follows the neutral **Master State v1** contract:
- Master credentials default location: `~/.config/samsung-account/master.json` (POSIX permissions `0600`).
- Seamless backwards compatibility: if no master file exists, it safely reads `~/.config/samsung-find/state.json` in read-only mode without modifying it.
- **Strictly Read-Only Transport**: All health document fetching strictly uses HTTPS `GET` requests against validated `*.samsungcloud.com` endpoints. It has no write, update, or mutation capabilities.

---

## Features

- **Typed Python SDK**: High-level `SamsungHealthClient` (online sync + read) and `SamsungHealthLocalClient` (offline mirror analytics).
- **Consolidated Analytics**: Built-in aggregations for daily activity (`step_daily_trend`), sleep stages, continuous heart rate, workouts, body weight, oxygen saturation, and stress.
- **Provenance & Formula Tracking**: Every derived metric explicitly publishes its mathematical calculation formula and evidence provenance.
- **Bundled Baseline Catalog**: Out-of-the-box support for standard Samsung Health data types even in pristine environments without an initial network sync.
- **Model Context Protocol (MCP) Server**: Privacy-preserving stdio MCP server (`samsung-health-mcp`) with bounded record retrieval and secret redaction.
- **Unified CLI (`samsung-health`)**: Structured versioned JSON output with standardized POSIX exit codes (`0`, `2`, `3`, `4`, `5`, `6`).

---

## Quick Start

### Installation

```bash
# Install core package
pip install samsung-health-cloud

# Install with MCP server support
pip install "samsung-health-cloud[mcp]"

# Install for local development
pip install "samsung-health-cloud[dev]"
```

### CLI Quick Start

```bash
# Verify environment, local catalog, SQLite mirror, and disk space
samsung-health doctor

# Check token presence and expiration timestamps (never logs secrets)
samsung-health status

# Synchronize recent health data (defaults to last 14 days)
samsung-health sync --days 14

# View multi-metric daily summary
samsung-health summary 2026-08-30

# Inspect specific daily metrics
samsung-health steps
samsung-health sleep
samsung-health heart-rate
samsung-health weight

# Advanced multi-period analytics
samsung-health analyze activity --period week --compare previous
samsung-health analyze sleep --latest
samsung-health analyze exercise --period month
```

---

## Python SDK Reference

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
samsung-health-mcp
```

### Registered Tools
| Tool Name | Scope | Description |
|---|---|---|
| `samsung_health_status` | Metadata | Safe token expiration status without secrets |
| `samsung_health_types` | Metadata | List supported health manifests and schema revisions |
| `samsung_health_inventory` | Local Cache | Record counts and temporal bounds per manifest |
| `samsung_health_analyze` | Analytics | Structured analytics for sleep, steps, exercise, or generic types |
| `samsung_health_summary` | Analytics | Multi-metric daily summary |
| `samsung_health_cache_status` | Mirror Status | SQLite database synchronization error counts |
| `samsung_health_read_records` | Raw Data | Bounded raw record inspection (clamped to max 50 records, strict redaction) |
| `samsung_health_sync` | Cloud Sync | Synchronize health records into local SQLite mirror |

For complete MCP configuration examples, see [`docs/mcp.md`](docs/mcp.md).

---

## CLI Reference & Exit Codes

The `samsung-health` CLI outputs versioned JSON envelopes (`{"ok": true, "schema_version": "1.0", "data": ...}`) by default.

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

- [Architecture & ADR 0001](docs/adr/0001-project-naming.md): Project naming and unified CLI taxonomy.
- [Authentication Architecture](docs/authentication.md): Samsung OAuth token exchange, SCSP registration, and Master State v1.
- [Privacy Policy & Safety](docs/privacy.md): Strict read-only boundaries, secret redaction, and local isolation.
- [Research Provenance](docs/research-provenance.md): Methodologies, evidence tiers, and verification limits.
- [Migration Guide](docs/migration-0.7.md): Migrating from legacy 0.6 setups to 0.7.0.
- [Python SDK Guide](docs/sdk.md): Facades, data models, and error hierarchy.
- [CLI Reference](docs/cli.md): Commands, arguments, envelopes, and exit codes.
- [MCP Reference](docs/mcp.md): Stdio server tools, bounding rules, and configuration.

---

## Privacy & Ethical Research

This project is built strictly for personal data sovereignty, transparency, and research.
- **No Private Data**: This repository contains strictly synthetic fixtures, non-personal baseline catalogs, and neutral statistical models.
- **No Live Network Calls in Tests**: All unit, contract, and integration tests run entirely against local mock transports or synthetic SQLite databases.
- **No Write Operations**: Health data transport endpoints are strictly verified to accept only `GET` operations.

---

## License

This project is licensed under the [MIT License](LICENSE).
