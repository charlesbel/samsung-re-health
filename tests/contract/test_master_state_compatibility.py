from pathlib import Path

import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.credentials import (
    MasterCredentials,
    load_master_credentials,
    resolve_master_state_path,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_load_master_credentials_v1_valid(tmp_path: Path):
    source = FIXTURES_DIR / "master-state-v1.synthetic.json"
    target = tmp_path / "master.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    target.chmod(0o600)

    creds = load_master_credentials(target)
    assert isinstance(creds, MasterCredentials)
    assert creds.token == "synthetic-master-token-xyz"
    assert creds.login_id == "synthetic-user@example.com"
    assert creds.physical_address == "synthetic-physical-addr"
    assert creds.auth_server_url == "https://eu-auth2.samsungosp.com"
    assert creds.user_id == "synthetic-uid-12345"
    assert creds.generation == "synthetic-gen-001"
    assert "synthetic-master-token-xyz" not in repr(creds)
    assert "synthetic-user@example.com" not in repr(creds)


def test_load_master_credentials_legacy_fallback(tmp_path: Path, monkeypatch):
    source = FIXTURES_DIR / "master-state-v1.legacy-sample.json"
    target = tmp_path / "state.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    target.chmod(0o600)

    creds = load_master_credentials(target)
    assert creds.token == "synthetic-legacy-token"
    assert creds.login_id == "synthetic-legacy@example.com"
    assert creds.physical_address == "synthetic-legacy-device"
    assert creds.auth_server_url == "https://eu-auth2.samsungosp.com"
    assert creds.user_id == "synthetic-legacy-user"


def test_load_master_credentials_rejects_symlink(tmp_path: Path):
    real_file = tmp_path / "real_master.json"
    real_file.write_text(
        (FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8")
    )
    real_file.chmod(0o600)

    symlink_file = tmp_path / "symlink_master.json"
    symlink_file.symlink_to(real_file)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):
        load_master_credentials(symlink_file)


def test_load_master_credentials_rejects_permissive_mode(tmp_path: Path):
    target = tmp_path / "master.json"
    target.write_text(
        (FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8")
    )
    target.chmod(0o666)

    with pytest.raises(SamsungHealthCloudError, match="permissions"):
        load_master_credentials(target)


def test_load_master_credentials_rejects_untrusted_authority(tmp_path: Path):
    target = tmp_path / "master.json"
    target.write_text(
        (FIXTURES_DIR / "master-state-v1.invalid-authority.json").read_text(
            encoding="utf-8"
        )
    )
    target.chmod(0o600)

    with pytest.raises(SamsungHealthCloudError, match="authority|host|domain|server"):
        load_master_credentials(target)


def test_load_master_credentials_exception_never_leaks_secrets_or_path(tmp_path: Path):
    target = tmp_path / "secret_subpath" / "master.json"
    target.parent.mkdir(mode=0o700, parents=True)
    target.write_text('{"invalid_json": true', encoding="utf-8")
    target.chmod(0o600)

    with pytest.raises(SamsungHealthCloudError) as exc_info:
        load_master_credentials(target)

    error_msg = str(exc_info.value)
    assert "secret_subpath" not in error_msg
    assert "master.json" not in error_msg


def test_resolve_master_state_path_priority(tmp_path: Path, monkeypatch):
    custom_injected = tmp_path / "injected.json"
    assert resolve_master_state_path(custom_injected) == custom_injected

    cli_arg = tmp_path / "cli_arg.json"
    assert resolve_master_state_path(None, cli_override=cli_arg) == cli_arg

    env_path = tmp_path / "env_master.json"
    monkeypatch.setenv("SAMSUNG_ACCOUNT_MASTER_STATE", str(env_path))
    assert resolve_master_state_path(None, cli_override=None) == env_path
