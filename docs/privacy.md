# Privacy and Data Protection

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd.

## Core Privacy Principles

1. **Strict Read-Only Design**: `samsung-re-health` is strictly a read-only client for personal health data. It possesses no capabilities to create, update, overwrite, or delete health records on Samsung Cloud servers (HTTPS `GET` only).
2. **Local-First Storage**: All cached data, sync states, and query results remain stored locally on your machine in user-controlled directories (`user_data_dir`, `user_state_dir`, `user_config_dir`). No telemetry, analytics, or remote logging services are embedded.
3. **No Embedded Third-Party Transmission**: The package embeds no telemetry, analytics, remote logging service, intermediary proxy, or vendor cloud. Direct SDK/CLI synchronization transfers data only between Samsung Cloud and the local client. MCP users deliberately transmit selected tool results to their configured MCP host/model; that host's operator, retention, and privacy policies therefore form an additional trust boundary.
4. **Secret Masking & Redaction**:
   - Access tokens, authorization headers, refresh tokens, CDIDs, and user identifiers are never printed to `stdout` or logs.
   - Internal Samsung identifiers and sensitive fields are masked by default in CLI outputs and MCP tool responses.
   - Dataclass string representations (`__repr__`) redact secret fields automatically.
5. **No Medical Inference**: The software does not attempt clinical diagnosis, readiness scoring, or medical judgments. Unverified or private fields are presented with neutral descriptive statistics only.
