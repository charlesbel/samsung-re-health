from pathlib import Path

import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.credentials import (
    MasterCredentials,
    default_master_state_path,
    legacy_find_state_path,
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
    assert creds.token == "synthetic-test-master-token-not-real"
    assert creds.login_id == "synthetic-test-user@example.invalid"
    assert creds.physical_address == "synthetic-test-physical-address"
    assert creds.auth_server_url == "https://synthetic-test.samsungosp.com"
    assert creds.user_id == "synthetic-test-user-id"
    assert creds.generation == "synthetic-test-generation-0001"
    assert "synthetic-test-master-token-not-real" not in repr(creds)
    assert "synthetic-test-user@example.invalid" not in repr(creds)


def test_load_master_credentials_legacy_fallback(tmp_path: Path):
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
    target.write_text((FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8"))
    target.chmod(0o666)

    with pytest.raises(SamsungHealthCloudError, match="permissions"):
        load_master_credentials(target)


def test_load_master_credentials_rejects_untrusted_authority(tmp_path: Path):
    target = tmp_path / "master.json"
    target.write_text(
        (FIXTURES_DIR / "master-state-v1.invalid-authority.json").read_text(encoding="utf-8")
    )
    target.chmod(0o600)

    with pytest.raises(SamsungHealthCloudError, match="authority|host|domain|server"):
        load_master_credentials(target)


def test_resolve_master_state_path_priority(tmp_path: Path, monkeypatch):
    custom_injected = tmp_path / "injected.json"
    assert resolve_master_state_path(custom_injected) == custom_injected

    cli_arg = tmp_path / "cli_arg.json"
    assert resolve_master_state_path(None, cli_override=cli_arg) == cli_arg

    env_path = tmp_path / "env_master.json"
    monkeypatch.setenv("SAMSUNG_ACCOUNT_MASTER_STATE", str(env_path))
    assert resolve_master_state_path(None, cli_override=None) == env_path


@pytest.mark.parametrize(
    ("platform", "master_relative", "legacy_relative"),
    [
        ("linux", Path("samsung-account/master.json"), Path("samsung-find/state.json")),
        (
            "darwin",
            Path("Library/Application Support/samsung-account/master.json"),
            Path("Library/Application Support/samsung-find/state.json"),
        ),
        ("win32", Path("samsung-account/master.json"), Path("samsung-find/state.json")),
    ],
)
def test_shared_master_and_legacy_paths_match_find_on_each_platform(
    tmp_path: Path,
    monkeypatch,
    platform: str,
    master_relative: Path,
    legacy_relative: Path,
):
    from samsung_health_cloud import credentials

    home = tmp_path / "home"
    xdg_config = tmp_path / "xdg-config"
    appdata = tmp_path / "roaming-appdata"
    monkeypatch.setattr(credentials.sys, "platform", platform)
    monkeypatch.setattr(credentials.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("APPDATA", str(appdata))

    if platform == "linux":
        root = xdg_config
    elif platform == "darwin":
        root = home
    else:
        root = appdata

    assert default_master_state_path() == root / master_relative
    assert legacy_find_state_path() == root / legacy_relative


def test_windows_shared_paths_fall_back_to_roaming_profile(tmp_path: Path, monkeypatch):
    from samsung_health_cloud import credentials

    home = tmp_path / "home"
    monkeypatch.setattr(credentials.sys, "platform", "win32")
    monkeypatch.setattr(credentials.Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("APPDATA", raising=False)

    expected = home / "AppData" / "Roaming"
    assert default_master_state_path() == expected / "samsung-account" / "master.json"
    assert legacy_find_state_path() == expected / "samsung-find" / "state.json"


def test_load_master_credentials_rejects_symlinked_parent_dir(tmp_path: Path):
    real_parent = tmp_path / "real_dir"
    real_parent.mkdir(mode=0o700)
    target = real_parent / "master.json"
    target.write_text((FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8"))
    target.chmod(0o600)

    sym_parent = tmp_path / "sym_dir"
    sym_parent.symlink_to(real_parent)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):
        load_master_credentials(sym_parent / "master.json")


def test_load_master_credentials_rejects_symlinked_lock_file(tmp_path: Path):
    target = tmp_path / "master.json"
    target.write_text((FIXTURES_DIR / "master-state-v1.synthetic.json").read_text(encoding="utf-8"))
    target.chmod(0o600)

    lock_file = tmp_path / "master.json.lock"
    lock_file.symlink_to(target)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):
        load_master_credentials(target)


def test_load_master_credentials_rejects_bool_numbers(tmp_path: Path):
    target = tmp_path / "master.json"
    payload = {
        "schema": "io.github.charlesbel.samsung-account.master",
        "schema_version": True,  # bool instead of int
        "generation": "gen-1",
        "created_at": 100,
        "updated_at": 100,
        "account": {"login_id": "u@ex.inv"},
        "installation": {"physical_address": "addr"},
        "identity": {
            "auth_server_url": "https://account.samsung.com",
            "userauth_token": "tok",
        },
    }
    import json

    target.write_text(json.dumps(payload), encoding="utf-8")
    target.chmod(0o600)

    with pytest.raises(SamsungHealthCloudError, match="version"):
        load_master_credentials(target)
