from pathlib import Path

SKILL_PATH = Path(__file__).parent.parent.parent / ".skills" / "samsung-health-cloud" / "SKILL.md"


def test_skill_manifest_exists_and_has_valid_frontmatter():
    assert SKILL_PATH.exists(), f"Skill file missing at {SKILL_PATH}"
    content = SKILL_PATH.read_text(encoding="utf-8")

    assert content.startswith("---")
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Frontmatter must be enclosed with ---"
    frontmatter = parts[1]
    assert "name: samsung-health-cloud" in frontmatter
    assert "description:" in frontmatter


def test_skill_manifest_contains_privacy_rules_and_workflows():
    content = SKILL_PATH.read_text(encoding="utf-8")

    # Strict privacy assertions
    assert "read-only" in content.lower()
    assert "secret" in content.lower()
    assert "token" in content.lower()

    # Workflows
    assert "samsung-health doctor" in content or "doctor" in content
    assert "SamsungHealthClient" in content
    assert "samsung_health_" in content  # MCP tools documented

    # Sanitization: ensure no maintainer paths
    assert "/home/" not in content
