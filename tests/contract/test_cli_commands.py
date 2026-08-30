import json
from pathlib import Path

import jsonschema
import pytest

from samsung_health_cloud import cli

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "cli" / "v1"


@pytest.fixture
def response_envelope_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "response-envelope.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def error_envelope_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "error-envelope.schema.json").read_text(encoding="utf-8"))


def test_cli_status_json_envelope(tmp_path: Path, capsys, response_envelope_schema):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        '{"user_id": "test-uid", "health_access_expires_at": 1000}', encoding="utf-8"
    )
    state_file.chmod(0o600)

    exit_code = cli.main(["--state", str(state_file), "status"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    jsonschema.validate(instance=payload, schema=response_envelope_schema)
    assert payload["ok"] is True
    assert payload["schema_version"] == "1.0"
    assert "user_id_present" in payload["data"]


def test_cli_types_json_envelope(tmp_path: Path, capsys, response_envelope_schema):
    exit_code = cli.main(["types"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    jsonschema.validate(instance=payload, schema=response_envelope_schema)
    assert payload["ok"] is True
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) > 0


def test_cli_error_envelope_and_exit_code(tmp_path: Path, capsys, error_envelope_schema):
    # Invalid argument combination
    exit_code = cli.main(["analyze", "sleep", "--period", "week"])
    assert exit_code == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    jsonschema.validate(instance=payload, schema=error_envelope_schema)
    assert payload["ok"] is False
    assert payload["error"]["code"] in ("invalid_arguments", "usage_error")


def test_cli_unknown_argument_produces_single_json_error(capsys, error_envelope_schema):
    exit_code = cli.main(["--nonexistent-flag"])
    assert exit_code == 2

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    jsonschema.validate(instance=payload, schema=error_envelope_schema)
    assert payload["ok"] is False
    assert payload["error"]["code"] in ("invalid_arguments", "usage_error")
    assert (
        "required" in payload["error"]["message"].lower()
        or "unrecognized" in payload["error"]["message"].lower()
    )


def test_cli_missing_positional_produces_single_json_error(capsys, error_envelope_schema):
    exit_code = cli.main(["data"])
    assert exit_code == 2

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    jsonschema.validate(instance=payload, schema=error_envelope_schema)
    assert payload["ok"] is False
    assert payload["error"]["code"] in ("invalid_arguments", "usage_error")
    assert "required" in payload["error"]["message"].lower()
