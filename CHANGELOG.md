# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.2] - 2026-09-30

### Fixed
- Updated nine verified Samsung Cloud schema revisions to restore synchronization after HTTP 400 schema-revision errors.
- Corrected known stale revisions when reading an existing private catalog, without modifying its file, routing metadata, manifest versions, or unrelated/custom revisions.
- Updated the bundled baseline catalog for the affected types and added synthetic synchronization and private-catalog preservation regressions.

### Security
- Updated the locked transitive PyJWT dependency to a patched release identified by the dependency audit.

## [0.7.1] - 2026-08-31

### Changed
- Reworked the README to explain direct Samsung Health Cloud synchronization, the incremental SQLite mirror, SDK/CLI/MCP access, and the project's relationship to the official Android SDK, Health Connect, mobile integration services, and export converters.
- Made bundled-skill installation instructions harness-neutral by requiring the agent runtime's configured skills directory instead of a framework-specific path.
- Clarified the boundaries between Samsung-reported values, observed private fields, locally derived analyses, structural coverage, and semantic validation.
- Refined the documented data flow and read boundary: cloud health documents are fetched without record mutation, while synchronization still writes local mirror and checkpoint state.

### Fixed
- Scoped MCP redaction guarantees separately from raw CLI and SDK outputs.
- Corrected endpoint-authority, provenance, release, migration, privacy, and offline-storage wording that could imply broader guarantees than the implementation provides.
- Added documentation contracts for product positioning and portable agent-skill installation.

## [0.7.0] - 2026-08-30

### Added
- **Shared Master State v1**: Validated use of the neutral `samsung-account/master.json` contract with symlink/permission checks, non-destructive legacy fallback, and an optional first-login bootstrap included in this package.
- **Typed SDK Facade**: Public `SamsungHealthClient` and offline `SamsungHealthLocalClient` facades exported from `samsung_health_cloud`.
- **Domain Models & Exceptions Hierarchy**: Typed dataclasses (`HealthConfig`, `DeviceProfile`, `MasterCredentials`, etc.) and structured exception hierarchy (`SamsungHealthError`, `AuthenticationError`, `NetworkError`, etc.).
- **Bundled Baseline Manifest Catalog**: Embedded `resources/manifests.json` providing immediate offline bootstrap and manifest resolution for common health types under empty environments without prior local file configuration.
- **Versioned JSON CLI Envelopes**: Machine-readable JSON envelopes (`ok`, `schema_version: "1.0"`, `data`, `meta`, `error`) and standardized process exit codes (0, 2, 3, 4, 5, 6).
- **Public Identity Harmonization**: Released as `samsung-re-health` on PyPI and GitHub (`charlesbel/samsung-re-health`), standardizing on the universal `samsung-re-{domain}` reverse-engineering ecosystem convention.
- **Canonical CLI & MCP Server**: `samsung-re-health` CLI and `samsung-re-health-mcp` stdio MCP server (`samsung-re-health`) exposing read-only analytical tools (`status`, `types`, `inventory`, `analyze`, `summary`, `cache_status`) and gated, bounded record inspection with redaction.
- **Root Portable Skill**: Public agent skill definition at `.skills/samsung-re-health/SKILL.md`.
- **Comprehensive Docs & Contract Schemas**: Formal JSON Schemas for master state v1 and CLI v1 envelopes, plus architecture, ADR, migration, privacy, and SDK documentation.

### Changed
- **CLI Architecture Separation**: Cleanly separated CLI argument parsing, domain services execution, and serialization layers.
- **Timezone & Profile Portability**: Replaced hardcoded timezone with configurable `timezone` (defaulting to `UTC`) and generalized device profiles.
- **Legacy Compatibility Aliases**: `samsung-health`, `samsung-health-cloud`, and `samsung-health-mcp` preserved as compatibility aliases, with CLI aliases emitting deprecation warnings to stderr.

### Security
- **Strict GET-Only Data Transport**: Enforced GET-only transport for cloud health data endpoints and restricted POST requests strictly to closed auth/SCSP endpoints.
- **Secret Redaction**: Added comprehensive secret masking across data models, loggers, exceptions, and MCP responses.

## [0.6.0] - 2026-08-28

### Added
- Initial operational client baseline supporting SCSP authentication, SQLite cache mirror, universal schema inspection, and analytics engine.
