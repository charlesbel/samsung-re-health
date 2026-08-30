# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-08-30

### Added
- **Shared Master State v1 Consumer**: Strict read-only consumption of the neutral `samsung-account/master.json` contract with symlink/permission checks and non-destructive legacy fallback.
- **Typed SDK Facade**: Public `SamsungHealthClient` and offline `SamsungHealthLocalClient` facades exported from `samsung_health_cloud`.
- **Domain Models & Exceptions Hierarchy**: Typed dataclasses (`HealthConfig`, `DeviceProfile`, `MasterCredentials`, etc.) and structured exception hierarchy (`SamsungHealthError`, `AuthenticationError`, `NetworkError`, etc.).
- **Bundled Baseline Manifest Catalog**: Embedded `resources/manifests.json` providing immediate offline bootstrap and manifest resolution for common health types under empty environments without prior local file configuration.
- **Versioned JSON CLI Envelopes**: Machine-readable JSON envelopes (`ok`, `schema_version: "1.0"`, `data`, `meta`, `error`) and standardized process exit codes (0, 2, 3, 4, 5, 6).
- **Stdio MCP Server**: `samsung-health-mcp` entry point exposing read-only analytical tools (`status`, `types`, `inventory`, `analyze`, `summary`, `cache_status`) and gated, bounded record inspection with redaction.
- **Root Portable Skill**: Public agent skill definition at `.skills/samsung-health-cloud/SKILL.md`.
- **Comprehensive Docs & Contract Schemas**: Formal JSON Schemas for master state v1 and CLI v1 envelopes, plus architecture, ADR, migration, privacy, and SDK documentation.

### Changed
- **CLI Architecture Separation**: Cleanly separated CLI argument parsing, domain services execution, and serialization layers.
- **Timezone & Profile Portability**: Replaced hardcoded timezone with configurable `timezone` (defaulting to `UTC`) and generalized device profiles.
- **Transitional CLI Alias**: `samsung-health-cloud` preserved as a transitional alias with a deprecation notice on stderr.

### Security
- **Strict GET-Only Data Transport**: Enforced GET-only transport for cloud health data endpoints and restricted POST requests strictly to closed auth/SCSP endpoints.
- **Secret Redaction**: Added comprehensive secret masking across data models, loggers, exceptions, and MCP responses.

## [0.6.0] - 2026-08-28

### Added
- Initial operational client baseline supporting SCSP authentication, SQLite cache mirror, universal schema inspection, and analytics engine.
