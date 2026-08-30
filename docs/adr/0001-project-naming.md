# ADR 0001: Ecosystem and Project Naming Conventions (`samsung-re-{domain}`)

## Status
Accepted

## Context
The Samsung reverse-engineering tools originally began as research scripts and internal agent tools (e.g. `samsung-find-agent` and private Samsung Health research workspaces). To publish these tools as stable, reusable open-source packages for developers, power users, and AI assistants, a clear, standardized public naming convention across the ecosystem must be established.

To make project non-affiliation explicit and immediately recognizable, the entire family of tools standardizes on the **`samsung-re-{domain}`** naming taxonomy (where `re` stands for *Reverse-Engineered*).

## Decision

The ecosystem adopts a universal convention for all present and future companion tools (`samsung-re-{domain}`):

### Universal Taxonomy

| Component | Standard Convention | Example (Health) | Example (Find) | Future Domain (`{domain}`) |
|---|---|---|---|---|
| **GitHub Repository** | `charlesbel/samsung-re-{domain}` | `charlesbel/samsung-re-health` | `charlesbel/samsung-re-find` | `charlesbel/samsung-re-{domain}` |
| **PyPI Distribution** | `samsung-re-{domain}` | `samsung-re-health` | `samsung-re-find` | `samsung-re-{domain}` |
| **Python Import** | Domain-specific stable snake_case | `samsung_health_cloud` | `samsung_find` | `samsung_{domain}` |
| **Canonical CLI** | `samsung-re-{domain}` | `samsung-re-health` | `samsung-re-find` | `samsung-re-{domain}` |
| **Canonical MCP** | `samsung-re-{domain}-mcp` | `samsung-re-health-mcp` | `samsung-re-find-mcp` | `samsung-re-{domain}-mcp` |
| **MCP Server Name** | `samsung-re-{domain}` | `samsung-re-health` | `samsung-re-find` | `samsung-re-{domain}` |
| **MCP Tool Prefix** | `samsung_{domain}_*` | `samsung_health_*` | `samsung_find_*` | `samsung_{domain}_*` |
| **Agent Skill Path** | `.skills/samsung-re-{domain}/SKILL.md` | `.skills/samsung-re-health/SKILL.md` | `.skills/samsung-re-find/SKILL.md` | `.skills/samsung-re-{domain}/SKILL.md` |
| **Standard Tagline** | `"Unofficial reverse-engineered Samsung {Domain} SDK, JSON CLI & MCP server"` | `"Unofficial reverse-engineered Samsung Health SDK, JSON CLI & MCP server"` | `"Unofficial reverse-engineered Samsung Find SDK, JSON CLI & MCP server"` | `"Unofficial reverse-engineered Samsung {Domain} SDK, JSON CLI & MCP server"` |

### Executables and Compatibility Matrix (Health)

| Surface | Canonical (0.7.0+) | Legacy Aliases (Deprecated with Warning) | Status |
|---|---|---|---|
| **CLI Command** | `samsung-re-health` | `samsung-health`, `samsung-health-cloud` | Canonical primary; aliases print stderr warning |
| **MCP Stdio Server** | `samsung-re-health-mcp` | `samsung-health-mcp` | Canonical primary; alias supported |
| **Python Module** | `samsung_health_cloud` | N/A | Preserved for API continuity and stability |
| **Local State Dir** | `~/.local/state/samsung-health-cloud` | N/A | Preserved to avoid breaking local mirror state |

### Rationale

1. **Explicit Non-Affiliation & Scope**: The `samsung-re-` prefix immediately signals to users, package registries, and distributors that the tooling is an unofficial reverse-engineered project, avoiding trademark confusion with official SDKs.
2. **Current Health Document Boundary**: Version 0.7 implements Health document downloads with `GET` requests and no cloud-record mutations. This audited client boundary is documented without claiming that Samsung's private services expose no other operations.
3. **Import & State Stability**: Internal Python import `samsung_health_cloud` and application data/state paths are intentionally maintained in this release to prevent breaking existing local SQLite mirrors and downstream script imports.
4. **Full Compatibility Transition**: Legacy CLI commands (`samsung-health`, `samsung-health-cloud`) and MCP command (`samsung-health-mcp`) remain functional entry points, emitting helpful deprecation notices directing users to canonical commands.

## Consequences

- Neutral **Master State v1** contract (`~/.config/samsung-account/master.json`) is shared cleanly between `samsung-re-find` and `samsung-re-health`.
- Consistency across all future `samsung-re-{domain}` tools.
- Zero breakage for existing users through legacy alias entry points.
