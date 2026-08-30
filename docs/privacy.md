# Privacy and Data Protection

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd.

## Core Privacy Principles

1. **Current Cloud-Record Scope**: The Health document client implemented in 0.7 uses HTTPS `GET` and does not create, update, or delete cloud health records. This describes the current package, not the complete capabilities of Samsung's private services. Future remote mutations must be separately designed, opt-in, and reviewed for data-loss and privacy risks.
2. **Local-First Storage**: All cached data, sync states, and query results remain stored locally on your machine in user-controlled directories (`user_data_dir`, `user_state_dir`, `user_config_dir`). No telemetry, analytics, or remote logging services are embedded.
3. **No Embedded Third-Party Transmission**: The package embeds no telemetry, analytics, remote logging service, intermediary proxy, or vendor cloud. Direct SDK/CLI synchronization transfers data only between Samsung Cloud and the local client. MCP users deliberately transmit selected tool results to their configured MCP host/model; that host's operator, retention, and privacy policies therefore form an additional trust boundary.
4. **Secret Masking & Redaction**:
   - Access tokens, authorization headers, refresh tokens, CDIDs, and user identifiers are never printed to `stdout` or logs.
   - Internal Samsung identifiers and sensitive fields are masked by default in CLI outputs and MCP tool responses.
   - Dataclass string representations (`__repr__`) redact secret fields automatically.
5. **No Medical Inference**: The software does not attempt clinical diagnosis, readiness scoring, or medical judgments. Unverified or private fields are presented with neutral descriptive statistics only.
