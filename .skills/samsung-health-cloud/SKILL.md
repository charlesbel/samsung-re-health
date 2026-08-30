---
name: samsung-health-cloud
description: Comprehensive operational skill for inspecting, synchronizing, querying, and analyzing personal Samsung Health Cloud data via CLI, Python SDK, and stdio MCP server.
---

# Samsung Health Cloud Skill

This skill provides comprehensive instructions and patterns for interacting with personal Samsung Health data using the `samsung-health-cloud` suite.

## Privacy and Safety Guarantees

1. **Strictly Read-Only**: The health data transport only issues HTTPS `GET` requests against validated `*.samsungcloud.com` endpoints.
2. **Credential Protection**: Never print, log, or export bearer tokens, refresh tokens, auth keys, or private notes. All CLI and MCP responses automatically redact secret strings.
3. **No Medical Claims**: Outputs provide mathematical summaries, interval aggregations, and formula provenance based on device logs; they do not provide clinical diagnoses or medical prescriptions.

## CLI Quick Reference

```bash
# Verify local installation, catalog, and permissions
samsung-health doctor

# Inspect authentication token status without exposing secrets
samsung-health status

# Refresh local SQLite mirror cache (default: 14 days)
samsung-health sync --days 14

# Get a consolidated summary for today or a specific date
samsung-health summary 2026-08-30

# Inspect specific daily metrics
samsung-health steps
samsung-health sleep
samsung-health heart-rate
samsung-health weight

# Advanced analysis with interval bounds
samsung-health analyze activity --period week --compare previous
samsung-health analyze sleep --latest
samsung-health analyze exercise --period month
```

## Python SDK Reference

```python
from samsung_health_cloud import (
    SamsungHealthClient,
    SamsungHealthLocalClient,
    HealthConfig,
)

# Offline local client (reads SQLite cache and bundled catalog)
config = HealthConfig()
with SamsungHealthLocalClient(config=config) as local:
    summary = local.summary(day="2026-08-30")
    sleep_report = local.analyze("sleep", latest=True)
    manifests = local.types()

# Online client (performs automatic token exchange and cloud synchronization)
with SamsungHealthClient(config=config) as client:
    sync_result = client.sync(days=7)
    status_info = client.status()
```

## Model Context Protocol (MCP) Server

The package includes a stdio MCP server exposing bounded, privacy-preserving tools:

- `samsung_health_status`: Inspect token expiration metadata safely.
- `samsung_health_types`: List supported health manifests and schema revisions.
- `samsung_health_inventory`: View record counts and time bounds in local mirror.
- `samsung_health_analyze`: High-level analytics for sleep, steps, exercise, or generic types.
- `samsung_health_summary`: Consolidated daily overview across key metrics.
- `samsung_health_cache_status`: Local mirror database statistics.
- `samsung_health_read_records`: Bounded raw record inspection with mandatory privacy masking.
- `samsung_health_sync`: Cloud synchronization into local SQLite mirror.

Launch the server over stdio:
```bash
samsung-health-mcp
```
