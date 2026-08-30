from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
PUBLIC_DOCS = (ROOT / "README.md").read_text(encoding="utf-8") + (
    ROOT / "docs" / "cli.md"
).read_text(encoding="utf-8")


def test_public_documentation_covers_every_cli_command() -> None:
    for command in (
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
        assert boundary in PUBLIC_DOCS


def test_readme_explains_install_auth_skills_and_read_only_scope() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install samsung-re-health" in readme
    assert "import remains `samsung_health_cloud`" in readme
    assert "samsung-re-find status" in readme
    assert ".skills/samsung-re-health" in readme
    assert "disabled" in readme or "absent unless" in readme
    assert "cannot create, update, or delete Health records" in readme


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
