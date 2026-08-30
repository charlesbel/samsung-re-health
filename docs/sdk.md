# Python SDK Reference

The `samsung_health_cloud` package exposes two primary typed client facades:

- `SamsungHealthClient`: Online client providing authentication, cloud synchronization, and local mirror analytics.
- `SamsungHealthLocalClient`: Offline-only client that reads from the local SQLite cache without initializing network transport or requiring cloud credentials.

## Basic Usage

```python
from samsung_health_cloud import (
    HealthConfig,
    SamsungHealthClient,
    SamsungHealthLocalClient,
)

# Offline analytics against local SQLite cache
with SamsungHealthLocalClient() as client:
    summary = client.summary()
    analysis = client.analyze(health_type="sleep", latest=True)
    print(f"Sleep efficiency: {analysis['headline']['efficiency_percent']}%")

# Online client with sync
config = HealthConfig(timezone="UTC")
with SamsungHealthClient(config=config) as client:
    status = client.status()
    print("Status:", status)

    # Synchronize sleep data and analyze
    sync_result = client.sync(manifest_id="com.samsung.health.sleep")
    analysis = client.analyze(health_type="sleep", latest=True)
```

## Public Facade Methods

### `SamsungHealthLocalClient`
- `doctor() -> dict`: Run offline environment and database diagnostics.
- `types(query: str | None = None) -> list[dict]`: List available health data types.
- `inventory(manifest_id: str | None = None) -> dict`: Inspect record counts and time bounds in local mirror.
- `cache_status() -> dict`: Query local SQLite mirror status and table sizes.
- `analyze(health_type: str, period: str | None = None, latest: bool = False, since: str | None = None, until: str | None = None, all_history: bool = False, compare: str | None = None) -> dict`: Perform high-level health analysis with formulas and provenance.
- `summary() -> dict`: Generate a unified health overview across sleep, activity, heart rate, and weight.
- `read_data(manifest_id: str, since: str | None = None, until: str | None = None, limit: int = 100, offset: int = 0, envelope: bool = False) -> list[dict]`: Read raw or parsed records from local mirror.

### `SamsungHealthClient` (inherits / extends with network)
- `status() -> dict`: Check token validity, expiry, and connection health.
- `sync(manifest_id: str | None = None, since: str | None = None) -> dict`: Sync specified manifest or all active manifests from Samsung Cloud.
