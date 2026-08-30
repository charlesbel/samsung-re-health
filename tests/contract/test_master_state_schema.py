import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "schemas" / "master-state-v1.schema.json"
)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def master_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_master_state_v1_valid_fixture_conforms(master_schema):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(instance=fixture, schema=master_schema)


def test_master_state_v1_future_version_rejected(master_schema):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.invalid-future-version.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=fixture, schema=master_schema)


def test_master_state_v1_invalid_authority_rejected(master_schema):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.invalid-authority.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=fixture, schema=master_schema)


@pytest.mark.parametrize(
    "tamper_fn",
    [
        lambda d: d.pop("schema"),
        lambda d: d.pop("generation"),
        lambda d: d["account"].pop("login_id"),
        lambda d: d["installation"].pop("physical_address"),
        lambda d: d["identity"].pop("userauth_token"),
        lambda d: d.update({"extra_key": "forbidden"}),
    ],
)
def test_master_state_v1_tampered_fixtures_rejected(master_schema, tamper_fn):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8")
    )
    tamper_fn(fixture)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=fixture, schema=master_schema)
