# Model Context Protocol (MCP) Server

`samsung-health-cloud` provides a Model Context Protocol (MCP) server over `stdio` (`samsung-health-mcp`) allowing AI assistants to query health data safely and with strict privacy boundaries.

## Installation

```bash
pip install 'samsung-health-cloud[mcp]'
```

## Configuration (e.g. for Claude Desktop or Hermes)

```json
{
  "mcpServers": {
    "samsung-health": {
      "command": "samsung-health-mcp",
      "args": []
    }
  }
}
```

## Default Tools (Read-Only & Aggregates)

- `samsung_health_status`: Check authentication state and token validity.
- `samsung_health_types`: List supported health data types and schemas.
- `samsung_health_inventory`: View record counts and available time ranges.
- `samsung_health_analyze`: Run structured analytics (sleep, activity, heart rate, weight) with formula provenance.
- `samsung_health_summary`: Generate a high-level health overview.
- `samsung_health_cache_status`: Inspect local SQLite cache size and synchronization metadata.

## Sensitive & Gated Tools

- `samsung_health_read_records`: Retrieve individual records with a hard server-enforced limit (max 50) and automatic redaction of internal URLs, hardware IDs, and private tokens.
- `samsung_health_sync`: Explicitly synchronize cloud records into the local database mirror.

## Privacy & Safety Guarantees

- **No Medical Claims**: Outputs never contain diagnostic claims or prescriptive clinical advice.
- **Redaction**: Raw tokens and signed URLs are masked before transmission.
- **Strict Bounding**: Pagination parameters are strictly validated and clamped.
