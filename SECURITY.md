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
3. **No Network Secret Leakage**: HTTP requests validate remote hostnames against closed Samsung endpoints. Tokens and headers are never written to stdout or uncaught exception strings.
4. **Local State Protections**: All derived local state files and caches are stored with strict POSIX permissions (`0600` for files, `0700` for parent directories) and reject symlinks or unexpected file ownership.
5. **Bounded MCP Interface**: The Model Context Protocol (MCP) server runs over `stdio` only (no exposed network ports), applies strict field redaction, and gates record reads behind explicit hard limits.
