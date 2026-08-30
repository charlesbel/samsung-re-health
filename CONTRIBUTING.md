# Contributing to samsung-re-health

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd.

Thank you for your interest in contributing to `samsung-re-health`!

## Code of Conduct & Ground Rules

1. **Strictly Synthetic Data Only**: Never commit real user account data, personal health measurements, real authentication tokens, or personal database dumps. All test fixtures and documentation examples must use synthetic data with obvious marker values.
2. **Current Cloud Boundary**: The current Health document client uses `GET` requests and does not modify cloud health records. New protocol work is welcome, including other operations, but remote mutations must be explicit, opt-in, isolated from existing read/sync commands, backed by reproducible evidence, and reviewed for data-loss and privacy risks.
3. **No Medical Claims**: This project provides neutral schema mapping, data extraction, and statistical aggregation. It does not provide medical diagnoses, clinical advice, or health interpretations.
4. **Test-Driven Development (TDD)**: Every bug fix and feature must include unit or contract tests. Follow TDD: write a focused failing test, observe the expected failure, implement the minimal fix, and verify green across the full suite.

## Development Workflow

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,mcp]"
```

### Running Tests and Linters

```bash
# Run test suite
pytest

# Check code formatting and linting
ruff check .
ruff format --check .

# Build distribution packages and verify
python -m build
twine check --strict dist/*
```

## Pull Request Guidelines

- Ensure `ruff check .` and `ruff format --check .` pass cleanly.
- Ensure all existing tests pass and new tests cover the added behavior.
- Document any schema or CLI contract changes in `CHANGELOG.md` and relevant `docs/` files.
- Double-check that no personal identifiers, tokens, or paths are included in commits.
