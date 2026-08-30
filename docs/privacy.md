# Privacy and Data Protection

## Core Privacy Principles

1. **Strict Read-Only Design**: `samsung-health-cloud` is strictly a read-only client for personal health data. It possesses no capabilities to create, update, overwrite, or delete health records on Samsung Cloud servers.
2. **Local-First Storage**: All cached data, sync states, and query results remain stored locally on your machine in user-controlled directories (`user_data_dir`, `user_state_dir`, `user_config_dir`). No telemetry, analytics, or remote logging services are embedded.
3. **No Third-Party Transmission**: Health data is transferred strictly over TLS between the official Samsung Cloud servers and your local client. No intermediary servers, proxies, or cloud platforms receive data.
4. **Secret Masking & Redaction**:
   - Access tokens, authorization headers, refresh tokens, CDIDs, and user identifiers are never printed to `stdout` or logs.
   - Internal Samsung identifiers and sensitive fields are masked by default in CLI outputs and MCP tool responses.
   - Dataclass string representations (`__repr__`) redact secret fields automatically.
5. **No Medical Inference**: The software does not attempt clinical diagnosis, readiness scoring, or medical judgments. Unverified or private fields are presented with neutral descriptive statistics only.
