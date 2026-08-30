# Samsung Health Python SDK

> **Disclaimer:** `samsung-re-health` is unofficial and reverse-engineered. The current client reads Health documents without modifying cloud records, and the private API can change without notice.

The distribution is `samsung-re-health`; import it as `samsung_health_cloud`. Python 3.11 or newer is required.

```bash
python -m pip install samsung-re-health
```

## Clients

- `SamsungHealthLocalClient`: offline-only facade over the local catalog and SQLite mirror. It does not initialize cloud authentication or network transport.
- `SamsungHealthClient`: adds Health OAuth/SCSP status and GET-based cloud synchronization, then exposes the same local analytics. Synchronization writes the local mirror and checkpoints.

Both are context managers and accept a portable `HealthConfig`.

## Offline Example

```python
from samsung_health_cloud import HealthConfig, SamsungHealthLocalClient

config = HealthConfig(timezone="Europe/Paris")
with SamsungHealthLocalClient(config=config) as client:
    diagnostics = client.doctor()
    manifests = client.types("sleep")
    inventory = client.inventory("sleep")
    analysis = client.analyze("sleep", latest=True)

    if analysis.get("available"):
        print("Reported efficiency:", analysis.get("reported_efficiency_percent"))
        print("Derived stage coverage:", analysis.get("derived_stage_coverage_percent"))
```

This reads only the local mirror. An empty new installation can resolve bundled catalog types but naturally has no personal records until an authorized synchronization populates the cache.

## Online Example

Create the neutral Samsung Account master-state v1 with `samsung-re-health auth-start` / `auth-complete`, or reuse a compatible master previously created by another `samsung-re-*` project:

```python
from samsung_health_cloud import HealthConfig, SamsungHealthClient

config = HealthConfig(timezone="UTC")
with SamsungHealthClient(config=config) as client:
    status = client.status()
    result = client.sync(days=7)
    analysis = client.analyze("activity", period="week", compare="previous")
```

`sync()` fetches Health documents through fixed validated HTTPS GET endpoints and writes only to the private local SQLite mirror. Authentication and SCSP session setup use narrow fixed endpoints but cannot create, update, or delete Health records.

## `SamsungHealthLocalClient`

### `doctor() -> dict[str, object]`

Checks local configuration, catalog, cache, permissions, and disk readiness without reading cloud credentials.

### `types(query: str | None = None) -> list[dict[str, object]]`

Lists or resolves catalog types by human name, suffix, or manifest identifier.

### `inventory(manifest_id: str | None = None) -> dict[str, object]`

Reports local record counts, temporal bounds, sync states, and coverage. A global call omits `manifest_id`.

### `cache_status() -> dict[str, object]`

Returns private mirror status and table/synchronization metadata.

### `summary(day: date | str | None = None) -> dict[str, object]`

Returns a consolidated view for one civil date in the configured timezone.

### `analyze(...) -> dict[str, object]`

```python
client.analyze(
    health_type,
    period=None,  # day, week, or month
    latest=False,
    since=None,  # ISO-8601
    until=None,  # ISO-8601
    all_history=False,
    compare=None,  # only "previous"
)
```

Selectors are mutually exclusive. Sleep supports latest/default only. Activity and exercise support civil periods, explicit intervals, all history, and appropriate previous-period comparisons. Generic catalog types support latest or one interval selector. Invalid combinations raise `UsageError` before credential or network access.

### `read_data(...) -> list[dict[str, Any]]`

```python
client.read_data(
    manifest_id,
    since=None,
    until=None,
    limit=100,  # 1..10000, booleans rejected
    offset=0,  # non-negative integer
    envelope=False,
)
```

This reads the local mirror only. Envelope mode can expose attachment metadata, signed URLs, E2EE markers, and unknown keys; protect its output as sensitive health data.

## `SamsungHealthClient`

The online client inherits all local methods.

### `status() -> dict[str, object]`

Reports token presence and expiry metadata without returning secret values.

### `sync(...) -> dict[str, object]`

```python
client.sync(
    manifest_id=None,
    days=14,  # integer 1..3650
    all_history=False,
    all_types=False,
    force=False,
)
```

A specific `manifest_id` cannot be combined with `all_types=True`. `all_history=True` cannot be combined with a non-default `days`. With no manifest and no `all_types`, the client synchronizes the core analysis types. The private service may ignore requested time bounds, so use full-history/all-type sync sparingly.

## Errors

Public exceptions inherit from `SamsungHealthError`:

- `UsageError`: invalid SDK or CLI arguments;
- `AuthenticationError`: missing, expired, revoked, or malformed authentication;
- `NetworkError`: transport failure;
- `RateLimitError`: server throttling;
- `DataError` / `SchemaError`: malformed or incompatible remote/local data;
- `StateError`: unsafe, corrupt, or inaccessible local state;
- `SamsungHealthCloudError`: general service/protocol error.

Validate user input before constructing an online client when practical. Never include raw remote bodies, tokens, cookies, authorization headers, or state contents in error reports.

## Interpretation Boundary

- `raw_observed` fields have structural presence but no approved semantic meaning or unit.
- Sleep `AWAKE` intervals are not conscious-awakening counts.
- Samsung-reported efficiency and locally derived stage coverage are different quantities.
- `time_window_only` joins indicate temporal overlap, not parentage or causality.
- Structural coverage is not medical or semantic completeness.
- Outputs are descriptive and must not be used as diagnosis or treatment advice.
