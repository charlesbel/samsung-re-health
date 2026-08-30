# samsung-re-health

[![CI](https://github.com/charlesbel/samsung-re-health/actions/workflows/ci.yml/badge.svg)](https://github.com/charlesbel/samsung-re-health/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/samsung-re-health.svg)](https://pypi.org/project/samsung-re-health/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

An unofficial Python SDK, JSON CLI and MCP server for Samsung Health Cloud.

`samsung-re-health` is a client for Samsung's private cloud synchronization protocol, not the official Android SDK. It downloads personal Samsung Health documents into a local SQLite mirror, then lets you query, export and analyze them without an Android emulator. It can also work entirely offline with an existing mirror.

> This project is reverse-engineered and is not affiliated with or endorsed by Samsung. It uses private APIs that may change without notice. Use it only with accounts and data you are authorized to access. Its analytics are descriptive and are not medical advice.

## What is included

- a Samsung Account setup flow and an online client for Health session initialization and cloud synchronization;
- an offline client for querying and analyzing a local mirror;
- a JSON CLI named `samsung-re-health`;
- a stdio MCP server named `samsung-re-health-mcp`;
- portable agent skills in `.skills/`.

Version 0.7 reads Health documents from Samsung Cloud with GET requests. It does not upload, edit or delete cloud health records. That is the current scope of this implementation, not a claim that Samsung's private services have no other operations. Authentication and session setup use separate technical POST requests to fixed Samsung hosts, while synchronization writes the local mirror and checkpoints. The project is designed to grow as contributors document and implement more of the protocol safely.

## Samsung RE projects

The `samsung-re-*` repositories are independent tools built around reverse-engineered Samsung services:

| Project | Install | Purpose |
| --- | --- | --- |
| [`samsung-re-find`](https://github.com/charlesbel/samsung-re-find) | `pip install samsung-re-find` | Devices, location, connectivity, ring and tracking |
| [`samsung-re-health`](https://github.com/charlesbel/samsung-re-health) | `pip install samsung-re-health` | Health Cloud synchronization, local queries and analytics |

Each project includes its own account-setup procedure. When both are installed, they reuse the same neutral Samsung Account master state while keeping their service tokens and data separate.

## Installation

Python 3.11 or newer is required. A virtual environment is recommended.

```bash
# SDK and CLI
python -m pip install samsung-re-health

# SDK, CLI and MCP server
python -m pip install 'samsung-re-health[mcp]'
```

To install from source:

```bash
git clone https://github.com/charlesbel/samsung-re-health.git
cd samsung-re-health
python -m pip install -e '.[dev,mcp]'
```

The distribution is named `samsung-re-health`; the Python import remains `samsung_health_cloud`. The old `samsung-health`, `samsung-health-cloud` and `samsung-health-mcp` executables are kept as temporary compatibility aliases.

Check the installation without credentials or network access:

```bash
samsung-re-health --version
samsung-re-health --help
samsung-re-health-mcp --help
```

## Account setup

Health includes its own Samsung Account setup. You do not need to install `samsung-re-find`.

On a Linux desktop:

```bash
# Register the private ms-app:// callback handler
samsung-re-health install-handler

# Generate a Samsung login URL, then open the URL in a browser
samsung-re-health auth-start --country us --locale en-US

# After the browser returns to the local handler
samsung-re-health auth-complete
samsung-re-health account-status

# Create or renew the Health-specific session
samsung-re-health init
samsung-re-health status
```

The browser login happens on Samsung's own page. This project never asks for or receives your password or second factor. `install-handler` currently uses `xdg-mime` and is Linux-specific. The package does not yet provide automatic callback helpers for macOS or Windows; those platforms require an independently configured private handler for the exact `ms-app://` callback.

The account flow stores a neutral `samsung-account/master.json` in the platform's user configuration directory. It is JSON protected by user-only filesystem permissions, not encrypted at rest. `samsung-re-find` uses the same format, so an existing master created by either project is reused automatically. The two packages do not import or require each other.

The online chain is: browser login → master authorization → Health OAuth tokens → SCSP registration and cloud token → document downloads → local SQLite mirror. `account-status` checks only the shared master; `status` checks the Health-specific session.

If you already have a local SQLite mirror and only want offline queries, you can skip account setup and `init`.

## CLI examples

Commands return versioned JSON envelopes by default.

```bash
# Check local files, catalog and free space
samsung-re-health doctor

# Download the most recent 14 days into the local mirror
samsung-re-health sync --days 14

# Query common daily views
samsung-re-health summary 2026-08-30
samsung-re-health steps 2026-08-30
samsung-re-health sleep 2026-08-30
samsung-re-health heart-rate 2026-08-30
samsung-re-health weight

# Explore the available data and observed fields
samsung-re-health types
samsung-re-health inventory
samsung-re-health schema

# Query or export one type
samsung-re-health data step_daily_trend --limit 100 --no-sync
samsung-re-health export com.samsung.shealth.step_daily_trend

# Run higher-level analyses
samsung-re-health analyze activity --period week --compare previous
samsung-re-health analyze sleep --latest
```

Synchronization reads cloud documents but writes the local SQLite mirror and local session/checkpoint files. Use `--no-sync` on supported query commands when you want a strictly offline read.

See [docs/cli.md](docs/cli.md) for every command, selector, output format and exit code.

## Python SDK

```python
from samsung_health_cloud import HealthConfig, SamsungHealthClient, SamsungHealthLocalClient

config = HealthConfig(timezone="UTC")

# Offline queries and analytics
with SamsungHealthLocalClient(config=config) as local:
    print(local.summary(day="2026-08-30"))
    print(local.analyze("sleep", latest=True))

# Online synchronization followed by the same local views
with SamsungHealthClient(config=config) as client:
    result = client.sync(days=7)
    print(result)
```

See [docs/sdk.md](docs/sdk.md) for the public clients, models and exceptions.

## MCP server

Start the six-tool default server with:

```bash
samsung-re-health-mcp
```

The default tools expose status, type metadata, inventory, aggregate analyses, daily summaries and cache status. Two more sensitive tools require explicit startup flags:

```bash
# Allow bounded access to individual health records
samsung-re-health-mcp --allow-records

# Allow network synchronization and local mirror updates
samsung-re-health-mcp --allow-sync
```

Raw-record access is gated because health records are personal and may be sent to the configured MCP host or model. Synchronization is gated because it contacts Samsung and changes local files. These safeguards describe the MCP interface, not limitations of Samsung's servers.

See [docs/mcp.md](docs/mcp.md) for tool names, schemas, limits and host configuration.

## Local files and privacy

The default locations are selected with `platformdirs`:

- `samsung-account/master.json`: reusable Samsung Account authorization;
- `samsung-health-cloud/state.json`: Health-specific tokens and registration state;
- `samsung-health-cloud/health.sqlite3`: local document mirror;
- `samsung-health-cloud/manifests.json`: observed and bundled type catalog.

The master state, Health state and mirror are separate. State files use private permissions where the platform supports POSIX modes and reject unsafe symlinks, but they are not encrypted at rest. Anyone able to bypass the user account's filesystem permissions may be able to read health records or reuse a session. The package has no telemetry or intermediary proxy.

MCP output is sent to whichever host or model you configure. Its retention and privacy policy are therefore part of your trust boundary. Direct CLI and SDK record reads do not apply every MCP-specific redaction rule.

Configuration paths and environment variables are documented in [docs/authentication.md](docs/authentication.md) and [docs/cli.md](docs/cli.md).

## How to interpret the data

Samsung Health schemas are private and evolve over time. The project separates fields whose meaning is understood from fields that are only observed structurally. Some aggregates are reported by Samsung; others are calculated locally and are labeled as such.

Keep these limits in mind:

- an observed field name does not prove its unit or medical meaning;
- records that overlap in time are not necessarily causally related;
- end-to-end encrypted documents and unsupported collections may be unavailable;
- a requested time range may not be honored by every private endpoint;
- summaries and trends are descriptive, not diagnostic.

Detailed formulas, provenance and field caveats are in [docs/research-provenance.md](docs/research-provenance.md) and the `schema` command.

The bundled catalog helps resolve known manifests locally; it does not guarantee that every type is available for every account, region or app version. Dedicated analyses exist for activity, sleep, exercise and common daily views. Other manifests use generic inventory, schema and statistical surfaces until their semantics are better understood.

## Current limitations

- **Samsung service:** account, region, app version and remote collection availability can change what is returned; private endpoints may change without notice.
- **Current implementation:** cloud health records are downloaded but not created, edited or deleted; callback installation is automated only on Linux; some document forms and E2E content are not decoded.
- **Reverse engineering:** many fields have observed structure but no verified meaning or unit, and a successful time-bounded request does not prove the server honored that range.
- **Local analysis:** a populated mirror can be analyzed offline, but copying master state or health data between machines is sensitive and is not an ordinary portability feature.

These limits describe observed service behavior and work still to be implemented; they are not a complete statement of Samsung's backend capabilities.

## Contributing

Pull requests are welcome for:

- newly documented manifests and fields;
- better decoders, joins and provenance;
- additional export and analysis methods;
- account and callback support on more platforms;
- other Samsung Health operations that have a clear contract and safety model.

The current cloud-record implementation is GET-only. A proposal that writes to Samsung Cloud must be explicit, opt-in, isolated from ordinary reads, backed by reproducible protocol evidence, and reviewed for data-loss and privacy risks. It must never turn an existing read or sync command into a remote mutation.

Tests must stay offline and use synthetic health data. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Documentation

- [Authentication and local state](docs/authentication.md)
- [CLI reference](docs/cli.md)
- [Python SDK](docs/sdk.md)
- [MCP server](docs/mcp.md)
- [Privacy](docs/privacy.md)
- [Research provenance](docs/research-provenance.md)
- [Migration to 0.7](docs/migration-0.7.md)
- [Release process](docs/release.md)

## License

MIT. See [LICENSE](LICENSE).
