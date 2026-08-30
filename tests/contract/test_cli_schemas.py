import json
from pathlib import Path

import jsonschema
import pytest

from samsung_health_cloud.serialization import envelope, error_envelope

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "cli" / "v1"


@pytest.fixture
def response_envelope_schema() -> dict:
    return json.loads(
        (SCHEMAS_DIR / "response-envelope.schema.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def error_envelope_schema() -> dict:
    return json.loads(
        (SCHEMAS_DIR / "error-envelope.schema.json").read_text(encoding="utf-8")
    )


def test_response_envelope_schema_validation(response_envelope_schema):
    payload = envelope({"count": 42, "items": ["a", "b"]}, meta={"execution_ms": 12})
    jsonschema.validate(instance=payload, schema=response_envelope_schema)
    assert payload["ok"] is True
    assert payload["schema_version"] == "1.0"
    assert payload["data"]["count"] == 42


def test_error_envelope_schema_validation(error_envelope_schema):
    payload = error_envelope(
        "auth_required", "Master authentication token is missing or expired"
    )
    jsonschema.validate(instance=payload, schema=error_envelope_schema)
    assert payload["ok"] is False
    assert payload["schema_version"] == "1.0"
    assert payload["error"]["code"] == "auth_required"
