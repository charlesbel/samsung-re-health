# Contributing to Samsung Health Cloud

Thank you for your interest in contributing to `samsung-health-cloud`!

## Code of Conduct & Ground Rules

1. **Strictly Synthetic Data Only**: Never commit real user account data, personal health measurements, real authentication tokens, or personal database dumps. All test fixtures and documentation examples must use synthetic data with obvious marker values.
2. **Read-Only Data Principle**: Data access is strictly `GET`-only. No write operations to Samsung Health cloud data may be introduced.
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
twine check dist/*
```

## Pull Request Guidelines

- Ensure `ruff check .` and `ruff format --check .` pass cleanly.
- Ensure all existing tests pass and new tests cover the added behavior.
- Document any schema or CLI contract changes in `CHANGELOG.md` and relevant `docs/` files.
- Double-check that no personal identifiers, tokens, or paths are included in commits.
