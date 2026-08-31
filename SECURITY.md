# Security Policy

## Reporting Security Issues

Please report security vulnerabilities and sensitive bugs privately. Do not open public GitHub issues for security vulnerabilities.

To report a vulnerability:
- Use GitHub Private Vulnerability Reporting on the repository.
- Alternatively, contact the maintainer directly.

### Critical Reminder: Do NOT Attach Health Data or Secrets

When submitting any report, log, or reproduction:
- **NEVER** include real Samsung Account credentials, refresh tokens, bearer tokens, or user IDs.
- **NEVER** attach personal health records, SQLite database files, or raw cloud synchronization dumps.
- Always use synthetic fixtures or sanitized reproduction steps.

## Security Architecture & Guarantees

`samsung-re-health` is engineered with the following security principles:

1. **Current Health-Document Boundary**: The Health document synchronization implemented in 0.7 uses `GET` requests and does not create, update, or delete cloud health records. This is the audited scope of the client, not a statement about every operation available on Samsung's private services.
2. **Master Credential Isolation**: An explicit account-setup command can create or replace the shared neutral `master.json`. Ordinary Health initialization and synchronization only read it, and master credentials are never copied into Health state or SQLite.
3. **Network Secret Handling**: Before project-owned code attaches credentials, it validates HTTPS authorities against closed Samsung allowlists. Normal CLI serializers and project exceptions omit known token/header values; raw process memory, debuggers, third-party tracing and caller-defined SDK logging are outside this guarantee.
4. **Local State Protections**: Account and derived-state stores reject unsafe symlinks/ownership and use private POSIX modes where supported. The SQLite mirror also requests private POSIX modes, but it does not implement every account-store path check. None of these files is encrypted at rest.
5. **Bounded MCP Interface**: The MCP server uses `stdio` (no inbound listener). Individual record reads are disabled by default, hard-limited and allowlist-redacted. Aggregate and summary tools can still disclose personal health information to the configured MCP client.
