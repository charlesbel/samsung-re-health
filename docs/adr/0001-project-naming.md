# ADR 0001: Ecosystem and Project Naming Conventions

## Status
Accepted

## Context
The Samsung reverse engineering tools initially existed as research scripts and internal agent tools (`samsung-find-agent` and a private Samsung Health research workspace). To publish these tools as stable, reusable open-source packages for developers, power users, and AI assistants, canonical naming conventions across Python distributions, module imports, command-line interfaces, and MCP servers must be established.

## Decision

The ecosystem is standardized around two companion repositories:

| Surface | Samsung Find | Samsung Health |
|---|---|---|
| GitHub Repository | `charlesbel/samsung-find` | `charlesbel/samsung-health-cloud` |
| Python Distribution | `samsung-find` | `samsung-health-cloud` |
| Python Import | `samsung_find` | `samsung_health_cloud` |
| Primary CLI Executable | `samsung-find` | `samsung-health` |
| Transitional CLI Alias | None | `samsung-health-cloud` (deprecated, preserved for 1 cycle) |
| MCP Executable | `samsung-find-mcp` | `samsung-health-mcp` |
| MCP Server Name | `samsung-find` | `samsung-health` |
| MCP Tool Prefix | `samsung_find_*` | `samsung_health_*` |
| Public Agent Skill | `.skills/samsung-find/SKILL.md` | `.skills/samsung-health-cloud/SKILL.md` |

### Rationale:
1. Retain `-cloud` in the Health package name (`samsung-health-cloud`) to differentiate this direct cloud API consumer from the legacy Android Health Data SDK, Health Connect wrappers, or offline CSV export parsers.
2. Keep import names `samsung_find` and `samsung_health_cloud` to preserve continuity and avoid unnecessary code churn.
3. Primary CLI command for Health is `samsung-health` with a transitional alias `samsung-health-cloud`.
4. Stdio MCP server is named `samsung-health-mcp`.

## Consequences
- Single shared master state format (`samsung-account/master.json`) without requiring a separate third authentication library initially.
- Transitionally preserve CLI compatibility while nudging users toward canonical commands.
