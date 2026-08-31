# Pre-Migration Baseline (Version 0.6.0)

## Overview
- **Package Name**: `samsung-health-cloud`
- **Initial Baseline Version**: 0.6.0
- **Test Suite**: 54 pytest test cases across 15 test modules
- **Declared minimum Python version**: >=3.11

## Initial Capabilities
- Single unified CLI handling commands: `init`, `status`, `doctor`, `types`, `inventory`, `schema`, `data`, `sync`, `analyze`, `summary`, `cache-status`.
- Local SQLite database caching raw documents and envelopes for fast querying.
- Multi-source de-duplication and time-window joins for sleep and daily activity.
- Provenance tracking distinguishing official documentation, schema conventions, decompiled APK references, and raw observed fields.

## Identified Gaps Prior to 0.7.0
1. No typed public SDK facade exposed at root `__init__.py`.
2. Hardcoded local timezone (`Europe/Paris`) and hardcoded device model strings.
3. No bundled baseline catalog, requiring existing local manifests file for discovery.
4. CLI mixed argument parsing, orchestration, and output rendering in a single module.
5. No formal JSON Schema validation for CLI envelopes or master credentials.
6. Lack of MCP server interface for AI agents.
7. Local maintainer paths and private references in documentation.
