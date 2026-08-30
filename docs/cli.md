# Command-Line Interface (CLI) Reference

## Executable

```bash
samsung-health [GLOBAL_OPTIONS] <COMMAND> [OPTIONS]
```

## Global Options

- `--master-state PATH`: Override path to Samsung Account master credentials.
- `--state PATH`: Override path to Health session state.
- `--catalog PATH`: Override path to manifests catalog.
- `--cache-db PATH`: Override path to SQLite mirror database.
- `--timezone TZ`: Specify timezone for date filters and day boundaries (default: `UTC`).
- `--output {json,jsonl,pretty}`: Output formatting (default: `json`).
- `--version`: Display version information and exit.

## Commands

### `status`
Inspect local token status and expiration timestamps without revealing secret values.
```bash
samsung-health status
```

### `doctor`
Verify local database health, permissions, catalog readiness, and disk space.
```bash
samsung-health doctor
```

### `types`
List registered health data manifests with resolution aliases.
```bash
samsung-health types [QUERY]
```

### `inventory`
Inspect local database record counts and date ranges.
```bash
samsung-health inventory [MANIFEST_ID]
```

### `analyze`
Perform high-level metric aggregation and provenance tracking.
```bash
samsung-health analyze sleep --latest
samsung-health analyze activity --period week
samsung-health analyze exercise --all-history
samsung-health analyze weight --latest
```

### `summary`
Generate a high-level overview across all core health metrics.
```bash
samsung-health summary
```

### `sync`
Synchronize data from Samsung Cloud into the local SQLite cache.
```bash
samsung-health sync [MANIFEST_ID]
```

### `data`
Query raw records from local cache (or sync before querying unless `--no-sync` is passed).
```bash
samsung-health data sleep --limit 10 --no-sync
```
