# Privacy and Data Protection

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd.

## Core Privacy Principles

1. **Current Cloud-Record Scope**: The Health document client implemented in 0.7 uses HTTPS `GET` and does not create, update, or delete cloud health records. This describes the current package, not the complete capabilities of Samsung's private services. Future remote mutations must be separately designed, opt-in, and reviewed for data-loss and privacy risks.
2. **Local Mirror, No Project Backend**: Health documents, sync state and derived session state are persisted in user-controlled local directories (`user_data_dir`, `user_state_dir`, `user_config_dir`). The project operates no intermediary backend, telemetry service or remote log collector. CLI output can be redirected to other files, and MCP results leave the process for the configured host/model.
3. **Explicit Data Flows**: Direct SDK/CLI synchronization transfers documents from Samsung Cloud to the local client. CLI/SDK callers decide where returned values are displayed or stored. MCP sends tool results to the configured MCP host/model, whose operator, retention and privacy policies form an additional trust boundary.
4. **Secret Masking & Redaction**:
   - Project-owned status/error envelopes mask known authentication tokens and authorization headers.
   - The gated MCP record reader applies an additional record-field allowlist. Other MCP aggregates can still contain personal health information.
   - Raw CLI/SDK reads and exports are not exhaustively redacted and must be treated as sensitive health-data exports.
   - Dataclass string representations (`__repr__`) redact secret fields automatically.
5. **No Clinical Claims**: Project-provided analyses are descriptive and do not diagnose or prescribe. Generic schema analysis gives unknown fields structural summaries without assigning a medical meaning; raw read/export interfaces may still return their original values.
