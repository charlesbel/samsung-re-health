from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILL_PATH = Path(__file__).parents[2] / ".skills" / "samsung-re-health" / "SKILL.md"


def _frontmatter(content: str) -> dict[str, str]:
    assert content.startswith("---\n")
    raw = content.split("---\n", 2)[1]
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if line and not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            values[key] = value.strip().strip('"')
    return values


def test_skill_manifest_is_public_portable_and_well_formed() -> None:
    content = SKILL_PATH.read_text(encoding="utf-8")
    metadata = _frontmatter(content)

    assert metadata["name"] == "samsung-re-health"
    assert metadata["description"].endswith(".")
    assert len(metadata["description"]) <= 60
    assert metadata["author"].startswith("Charles Bel")
    assert metadata["platforms"] == "[linux, macos, windows]"
    assert "/home/" not in content
    assert "## Pitfalls" in content
    assert "## Verification" in content


def test_skill_covers_cli_mcp_privacy_and_semantics() -> None:
    content = SKILL_PATH.read_text(encoding="utf-8")

    for command in (
        "doctor",
        "cache-status",
        "types",
        "analyze",
        "inventory",
        "schema",
        "data",
        "sync",
    ):
        assert command in content
    for selector in ("--latest", "--period", "--since", "--until", "--all-history", "--no-sync"):
        assert selector in content
    for tool in (
        "samsung_health_status",
        "samsung_health_types",
        "samsung_health_inventory",
        "samsung_health_analyze",
        "samsung_health_summary",
        "samsung_health_cache_status",
        "samsung_health_read_records",
        "samsung_health_sync",
    ):
        assert tool in content
    for boundary in (
        "--allow-records",
        "--allow-sync",
        "read-only",
        "raw_observed",
        "reported_efficiency_percent",
        "derived_stage_coverage_percent",
        "time_window_only",
        "coverage_percent == 100",
        "GET",
        "PUT",
        "PATCH",
        "DELETE",
    ):
        assert boundary in content


def test_documented_help_surfaces_work_in_empty_home(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")

    probes = (
        [sys.executable, "-m", "samsung_health_cloud.cli", "--help"],
        [sys.executable, "-m", "samsung_health_cloud.cli", "analyze", "--help"],
        [sys.executable, "-m", "samsung_health_cloud.cli", "data", "--help"],
        [sys.executable, "-m", "samsung_health_cloud.mcp_server", "--help"],
    )
    for probe in probes:
        completed = subprocess.run(
            probe, env=env, text=True, capture_output=True, timeout=15, check=False
        )
        assert completed.returncode == 0, completed.stderr
        assert "Traceback" not in completed.stderr
        assert "legacy Samsung Find state" not in completed.stderr
