import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "master-state-v1.schema.json"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

CANONICAL_SCHEMA_SHA256 = "c4cc1c62937200fbb95d2def0b39f3aa4db61ac2cc761a6bbb4591cca3a8c183"
CANONICAL_SYNTHETIC_SHA256 = "3381a2b1b4d4bda636c4364d0896cdba5bb2bfbf00f3b459ec559ad673dd0dca"


@pytest.fixture
def master_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_master_state_v1_canonical_sha256_hashes():
    schema_bytes = SCHEMA_PATH.read_bytes()
    assert hashlib.sha256(schema_bytes).hexdigest() == CANONICAL_SCHEMA_SHA256

    synthetic_bytes = (FIXTURES_DIR / "master-state-v1.synthetic.json").read_bytes()
    assert hashlib.sha256(synthetic_bytes).hexdigest() == CANONICAL_SYNTHETIC_SHA256


def test_master_state_v1_valid_fixture_conforms(master_schema):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(instance=fixture, schema=master_schema)


def test_master_state_v1_future_version_rejected(master_schema):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.invalid-future-version.json").read_text(encoding="utf-8")
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=fixture, schema=master_schema)


def test_master_state_v1_invalid_authority_rejected(master_schema):
    fixture = json.loads(
        (FIXTURES_DIR / "master-state-v1.invalid-authority.json").read_text(encoding="utf-8")
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
