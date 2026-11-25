# Model Context Protocol (MCP) Server

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd. Its current Health document client reads cloud records with GET requests and does not modify them.

`samsung-re-health-mcp` provides the same MCP tools over stdio (the default) and Streamable HTTP. Every enabled result can contain personal health information and is sent to the configured MCP client.

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

## Streamable HTTP

```bash
samsung-re-health-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Configure the MCP client to connect to `http://127.0.0.1:8000/mcp`. The example uses the default HTTP bind address and port. Tool flags work in either transport.

HTTP mode accepts the bind address as the request host. Use `--allowed-host` to add an exact HTTP Host header value, including the port if the client sends one. An explicit allowed host is required for wildcard binds such as `0.0.0.0`. Requests carrying an Origin header are rejected. For network access, put the listener behind an authenticated HTTPS proxy and restrict direct access to the listener.

## Default Tools (Read-Only & Aggregates)

- `samsung_health_status`: Inspect locally stored authentication presence and expiry metadata; this does not prove that Samsung has not revoked the token.
- `samsung_health_types`: List supported health data types and schemas.
- `samsung_health_inventory`: View record counts and available time ranges.
- `samsung_health_analyze`: Run structured analytics (sleep, activity, heart rate, weight) with formula provenance.
- `samsung_health_summary`: Generate a high-level health overview.
- `samsung_health_cache_status`: Inspect local SQLite cache size and synchronization metadata.

## Sensitive & Gated Tools

- `samsung_health_read_records`: Retrieve individual records with a hard server-enforced limit (max 50) and automatic redaction of internal URLs, hardware IDs, and private tokens. Enabled only with `--allow-records`.
- `samsung_health_sync`: Explicitly synchronize cloud records into the local database mirror. Enabled only with `--allow-sync`.

Although synchronization uses read-only `GET` requests against Samsung Health, it writes the local SQLite mirror and synchronization checkpoints and may refresh derived authentication state. Its MCP effect annotations are therefore `readOnlyHint=false`, `idempotentHint=false`, `destructiveHint=false`, and `openWorldHint=true`. The first two describe the complete local operation, not just the remote HTTP method; `destructiveHint=false` preserves the read-only Health-record boundary.

## Privacy and Effect Boundaries

- **Current record boundary**: Health document synchronization uses HTTPS `GET`; SCSP endpoints are fixed, the account authority is runtime-supplied but allowlisted, and sync writes the local mirror.
- **Clinical scope**: Project-provided analyses are descriptive, not diagnostic or prescriptive. Raw records can still contain vendor-authored labels or free text.
- **Redaction**: Project-owned token fields are masked. The gated individual-record tool additionally allowlists fields; aggregate tools are not anonymized.
- **Strict Bounding**: Pagination parameters are strictly validated; out-of-range values are rejected rather than silently clamped.
