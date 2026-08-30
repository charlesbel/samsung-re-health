# Model Context Protocol (MCP) Server

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd. Its current Health document client reads cloud records with GET requests and does not modify them.

`samsung-re-health` provides a Model Context Protocol (MCP) server over `stdio` (`samsung-re-health-mcp`) allowing AI assistants to query health data safely and with strict privacy boundaries.

## Installation

```bash
pip install 'samsung-re-health[mcp]'
```

## Configuration (e.g. for Claude Desktop or Hermes)

```json
{
  "mcpServers": {
    "samsung-re-health": {
      "command": "samsung-re-health-mcp",
      "args": []
    }
  }
}
```

> **Compatibility Note**: The legacy alias `samsung-health-mcp` is also supported for backward compatibility.

## Default Tools (Read-Only & Aggregates)

- `samsung_health_status`: Check authentication state and token validity.
- `samsung_health_types`: List supported health data types and schemas.
- `samsung_health_inventory`: View record counts and available time ranges.
- `samsung_health_analyze`: Run structured analytics (sleep, activity, heart rate, weight) with formula provenance.
- `samsung_health_summary`: Generate a high-level health overview.
- `samsung_health_cache_status`: Inspect local SQLite cache size and synchronization metadata.

## Sensitive & Gated Tools

- `samsung_health_read_records`: Retrieve individual records with a hard server-enforced limit (max 50) and automatic redaction of internal URLs, hardware IDs, and private tokens. Enabled only with `--allow-records`.
- `samsung_health_sync`: Explicitly synchronize cloud records into the local database mirror. Enabled only with `--allow-sync`.

Although synchronization uses read-only `GET` requests against Samsung Health, it writes the local SQLite mirror and synchronization checkpoints and may refresh derived authentication state. Its MCP effect annotations are therefore `readOnlyHint=false`, `idempotentHint=false`, `destructiveHint=false`, and `openWorldHint=true`. The first two describe the complete local operation, not just the remote HTTP method; `destructiveHint=false` preserves the read-only Health-record boundary.

## Privacy & Safety Guarantees

- **Current record boundary**: Health document synchronization uses HTTPS `GET`; authentication uses separate fixed technical endpoints, and sync writes the local mirror.
- **No Medical Claims**: Outputs never contain diagnostic claims or prescriptive clinical advice.
- **Redaction**: Raw tokens, authorization headers, and signed URLs are masked before transmission.
- **Strict Bounding**: Pagination parameters are strictly validated; out-of-range values are rejected rather than silently clamped.
