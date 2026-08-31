# Migration Guide: 0.6.x to 0.7.0 (`samsung-re-health`)

## Key Changes in 0.7.0

### 1. Public Identity & Package Distribution
- The project is officially distributed on PyPI as **`samsung-re-health`** (conforming to the universal `samsung-re-{domain}` ecosystem convention alongside `samsung-re-find`).
- Python library import name remains **`samsung_health_cloud`** to ensure full backwards compatibility for existing scripts.

### 2. Canonical CLI & MCP Entry Points
- The canonical CLI command is **`samsung-re-health`**.
- The canonical MCP stdio server executable is **`samsung-re-health-mcp`** (MCP server name: `samsung-re-health`).
- **Legacy Aliases**: Previous command names (`samsung-health`, `samsung-health-cloud`, `samsung-health-mcp`) remain available as compatibility aliases during the 0.7.x lifecycle, with CLI aliases emitting a deprecation notice to `stderr`.

### 3. Shared Master State v1 Contract
- Samsung Health now reads credentials from the shared neutral `master.json` file located by default at:
  - Linux: `~/.config/samsung-account/master.json` (or `$XDG_CONFIG_HOME/samsung-account/master.json`)
  - macOS: `~/Library/Application Support/samsung-account/master.json`
  - Windows: `%APPDATA%\samsung-account\master.json`
- **Backward Compatibility**: If `master.json` is not found, the client safely falls back to the matching legacy Find authentication state: `$XDG_CONFIG_HOME/samsung-find/state.json` on Linux, `~/Library/Application Support/samsung-find/state.json` on macOS, or `%APPDATA%\samsung-find\state.json` on Windows.
- **Fail-closed lineage migration**: pre-0.7 derived Health state with no `master_generation` is cleared and reinitialized before adopting Master State v1. Only an empty derived state can adopt the generation without invalidation.

### 4. Configurable Timezone & Defaults
- In 0.6.x, the timezone defaulted implicitly to `Europe/Paris`.
- In 0.7.0, the public default timezone is `UTC`.
- Users and scripts wishing to use a local timezone can pass `--timezone Europe/Paris` or set the `SAMSUNG_HEALTH_TIMEZONE` environment variable.

### 5. Machine-Readable JSON Output by Default
- CLI commands output versioned JSON envelopes (`{"ok": true, "schema_version": "1.0", "data": ...}`) by default on `stdout`.
- Exit codes now adhere to standard exit statuses:
  - `0`: Success
  - `2`: Invalid argument or usage error
  - `3`: Authentication required or invalid credentials
  - `4`: Remote network or protocol error
  - `5`: Permission or local filesystem error
  - `6`: Partial result

### 6. Bundled Runtime Catalog
- In 0.6.x, commands failed if no local manifest catalog had been created.
- In 0.7.0, a bundled baseline catalog provides known manifest identifiers for common types (`sleep`, `heart_rate`, `oxygen_saturation`, `exercise`, `steps`, `weight`, etc.). It enables local type resolution but does not guarantee account/region availability, complete decoding or verified semantics for every field.
