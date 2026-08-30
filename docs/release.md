# Release Process and Verification Gates

This document describes releases for `samsung-re-health`.

## Release Boundary

- Distribution: `samsung-re-health`
- Python import: `samsung_health_cloud`
- Canonical executables: `samsung-re-health`, `samsung-re-health-mcp`
- Trigger: a pushed tag exactly matching `{project.version}`
- Publisher: GitHub Actions OIDC through PyPI Trusted Publishing
- GitHub environment: `pypi`

No password, Health credential, or long-lived PyPI token belongs in the repository or workflow.

## Required Local Gates

After the final code or documentation edit, run both test modes, Ruff lint/format, `git diff --check`, wheel/sdist build, strict Twine metadata checks, dependency audit, `actionlint`, full-history Gitleaks with redaction, and `scripts/verify_privacy.py`. Install the built wheel with its MCP extra in an empty Python 3.11 environment and run `scripts/smoke_wheel_mcp.py`.

All tests and protocol smokes must use synthetic state and isolated `HOME`/XDG paths. Never run release checks against real credentials or health records.

## Automated Flow

`.github/workflows/release.yml` performs:

1. **`verify-release`**: full-history checkout, tag/version equality, dependencies, Ruff, standard and optimized tests, build, strict Twine checks, installed-wheel MCP/CLI smoke, privacy/archive inspection, `pip-audit`, and full-history Gitleaks.
2. **`publish-pypi`**: downloads the exact verified artifacts and publishes through Trusted Publishing only for an exact numeric SemVer tag.
3. **`github-release`**: runs only after PyPI publication succeeds and attaches those same artifacts to the final GitHub Release.

A manual workflow dispatch accepts an existing immutable `release_tag`, checks out that tag, verifies that it points to the tested commit, and publishes only when `publish_to_pypi` is explicitly enabled.

## Trusted Publisher Configuration

For the first release, configure a pending PyPI publisher with:

- PyPI project: `samsung-re-health`
- GitHub owner: `charlesbel`
- Repository: `samsung-re-health`
- Workflow: `release.yml`
- Environment: `pypi`

Create the GitHub `pypi` environment before tagging. Optional reviewers are an external repository setting.

## Publish

After the release commit is on `main`, CI is green, and the pending publisher exists:

```bash
git tag -a 0.7.0 -m "samsung-re-health 0.7.0"
git push origin 0.7.0
```

Do not upload manually in parallel. PyPI artifacts and versions are immutable; inspect remote state before any retry after partial failure.

## Post-Release Verification

Confirm that PyPI reports version `0.7.0` and both artifacts, install `samsung-re-health[mcp]==0.7.0` from PyPI in a fresh environment, run canonical CLI/MCP help and stdio negotiation, and verify a non-draft GitHub `0.7.0` release with matching assets and repository links.
