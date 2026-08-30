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

1. **Read-Only Data Transport**: Health data synchronization is strictly `GET`-only. The client cannot and does not write, modify, or delete health records in Samsung Cloud.
2. **Master Credential Isolation**: The client consumes the shared neutral `master.json` strictly in read-only mode. It never writes to or alters the master state.
3. **No Network Secret Leakage**: HTTP requests validate remote hostnames against closed Samsung endpoints. Tokens and headers are never written to stdout or uncaught exception strings.
4. **Local State Protections**: All derived local state files and caches are stored with strict POSIX permissions (`0600` for files, `0700` for parent directories) and reject symlinks or unexpected file ownership.
5. **Bounded MCP Interface**: The Model Context Protocol (MCP) server runs over `stdio` only (no exposed network ports), applies strict field redaction, and gates record reads behind explicit hard limits.
