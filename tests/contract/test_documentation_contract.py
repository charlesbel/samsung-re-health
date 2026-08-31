from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
PUBLIC_DOCS = (ROOT / "README.md").read_text(encoding="utf-8") + (
    ROOT / "docs" / "cli.md"
).read_text(encoding="utf-8")
SEMANTICS_DOCS = (ROOT / "docs" / "research-provenance.md").read_text(encoding="utf-8") + (
    ROOT / ".skills" / "samsung-re-health" / "SKILL.md"
).read_text(encoding="utf-8")
ALL_PUBLIC_MARKDOWN = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    )
)


def test_public_documentation_covers_every_cli_command() -> None:
    for command in (
        "install-handler",
        "auth-start",
        "auth-complete",
        "account-status",
        "init",
        "status",
        "doctor",
        "manifests",
        "read",
        "export",
        "export-all",
        "documents",
        "summary",
        "steps",
        "sleep",
        "heart-rate",
        "weight",
        "sync",
        "cache-status",
        "types",
        "data",
        "inventory",
        "schema",
        "analyze",
    ):
        assert command in PUBLIC_DOCS


def test_public_documentation_covers_sensitive_selectors_and_boundaries() -> None:
    for option in (
        "--all",
        "--e2ee-state",
        "--page-size",
        "--stop-on-error",
        "--schema-revision",
        "--page-token",
        "--no-sync",
        "--all-history",
        "--all-types",
        "--force",
        "--envelope",
        "--offset",
        "--compare",
        "--latest",
        "--period",
        "--allow-records",
        "--allow-sync",
    ):
        assert option in PUBLIC_DOCS
    for boundary in (
        "raw_observed",
        "reported_efficiency_percent",
        "derived_stage_coverage_percent",
        "time_window_only",
        "coverage_percent == 100",
    ):
        assert boundary in SEMANTICS_DOCS


def test_readme_explains_install_independent_auth_skills_and_current_scope() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install samsung-re-health" in readme
    assert "import remains `samsung_health_cloud`" in readme
    assert "You do not need to install `samsung-re-find`" in readme
    assert "samsung-re-health auth-start" in readme
    assert "samsung-re-health auth-complete" in readme
    assert "samsung-re-health account-status" in readme
    assert "portable agent skills in `.skills/`" in readme
    assert "current scope of this implementation" in readme
    assert "not a claim that Samsung's private services have no other operations" in readme
    assert "Pull requests are welcome" in readme
    assert "samsung-re-find status" not in readme
    assert "## Why this project exists" in readme
    assert "Samsung Health Data SDK" in readme
    assert "Health Connect" in readme
    assert "If you are an AI agent" in readme
    assert 'AGENT_SKILLS_DIR="/path/configured/by/your-agent"' in readme
    assert 'cp -R .skills/samsung-re-health "$AGENT_SKILLS_DIR/"' in readme
    assert 'cp -R .skills/samsung-account-auth "$AGENT_SKILLS_DIR/"' in readme
    assert "~/.hermes/skills" not in readme


def test_public_documentation_never_requires_find_for_health_bootstrap() -> None:
    lowered = ALL_PUBLIC_MARKDOWN.lower()
    assert "master-state v1 created by `samsung-re-find` is required" not in lowered
    assert "requires `samsung-re-find`" not in lowered
    assert "must install `samsung-re-find`" not in lowered


def test_authentication_docs_publish_exact_cross_platform_shared_paths() -> None:
    docs = (ROOT / "docs" / "authentication.md").read_text(encoding="utf-8")
    for path in (
        "$XDG_CONFIG_HOME/samsung-account/master.json",
        "$XDG_CONFIG_HOME/samsung-find/state.json",
        "~/Library/Application Support/samsung-account/master.json",
        "~/Library/Application Support/samsung-find/state.json",
        r"%APPDATA%\samsung-account\master.json",
        r"%APPDATA%\samsung-find\state.json",
    ):
        assert path in docs


def test_mcp_docs_explain_sync_effect_annotations() -> None:
    docs = (ROOT / "docs" / "mcp.md").read_text(encoding="utf-8")
    assert "`readOnlyHint=false`" in docs
    assert "`idempotentHint=false`" in docs
    assert "`destructiveHint=false`" in docs
    assert "`openWorldHint=true`" in docs


def test_docs_explain_sqlite_refresh_and_external_scheduler_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cli_docs = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    for docs in (readme, cli_docs):
        assert "SQLite" in docs
        assert "no built-in daemon or scheduler" in docs or "does not install a daemon" in docs
        assert "sync --all-types --days 14" in docs
        assert "sync --all-types --all-history --force" in docs
        assert (
            "Deleting an external scheduled task" in docs
            or "Removing an external scheduler" in docs
        )
