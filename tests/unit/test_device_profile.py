import json
from pathlib import Path

import pytest

from samsung_health_cloud import HealthConfig, cli
from samsung_health_cloud.exceptions import UsageError
from samsung_health_cloud.models import DeviceProfile


def test_device_profile_generic_defaults():
    profile = DeviceProfile()
    assert profile.model_name == "SM-GENERIC"
    assert profile.alias == "Samsung Health Cloud Client"
    assert profile.country_code == "USA"
    assert profile.android_sdk == "34"
    assert profile.android_release == "14"
    assert profile.platform_version == "6.0.0"
    assert profile.device_type == "phone"
    assert profile.client_tag == "ANDROID"


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("model_name", ""),
        ("model_name", "A" * 101),
        ("model_name", "SM\nBAD"),
        ("alias", ""),
        ("alias", "Alias\r\nBad"),
        ("country_code", "US"),
        ("country_code", "USAA"),
        ("country_code", "usa"),
        ("country_code", "123"),
        ("android_sdk", "abc"),
        ("android_sdk", "-1"),
        ("android_sdk", "1000"),
        ("device_type", "toaster"),
        ("client_tag", "WINDOWS"),
    ],
)
def test_device_profile_field_validation(field: str, bad_value: str):
    kwargs = {field: bad_value}
    with pytest.raises(ValueError):
        DeviceProfile(**kwargs)


def test_health_config_from_env_profile_overrides(monkeypatch):
    monkeypatch.setenv("SAMSUNG_HEALTH_DEVICE_MODEL", "SM-TEST999")
    monkeypatch.setenv("SAMSUNG_HEALTH_DEVICE_ALIAS", "Custom Test Alias")
    monkeypatch.setenv("SAMSUNG_HEALTH_COUNTRY_CODE", "FRA")
    monkeypatch.setenv("SAMSUNG_HEALTH_ANDROID_SDK", "35")
    monkeypatch.setenv("SAMSUNG_HEALTH_ANDROID_RELEASE", "15")
    monkeypatch.setenv("SAMSUNG_HEALTH_PLATFORM_VERSION", "7.0.0")
    monkeypatch.setenv("SAMSUNG_HEALTH_DEVICE_TYPE", "tablet")

    config = HealthConfig.from_env()
    p = config.device_profile
    assert p.model_name == "SM-TEST999"
    assert p.alias == "Custom Test Alias"
    assert p.country_code == "FRA"
    assert p.android_sdk == "35"
    assert p.android_release == "15"
    assert p.platform_version == "7.0.0"
    assert p.device_type == "tablet"


def test_health_config_from_env_invalid_profile_raises_usage_error(monkeypatch):
    monkeypatch.setenv("SAMSUNG_HEALTH_COUNTRY_CODE", "invalid_long_code")
    with pytest.raises(UsageError, match="device profile"):
        HealthConfig.from_env()


def test_cli_device_profile_options_propagation(tmp_path: Path):
    # Verify CLI parses and constructs profile without error
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    state_file.chmod(0o600)

    exit_code = cli.main(
        [
            "--state",
            str(state_file),
            "--device-model",
            "SM-CUSTOM01",
            "--device-alias",
            "My Device",
            "--country-code",
            "DEU",
            "status",
        ]
    )
    assert exit_code == 0


def test_cli_invalid_device_profile_option_produces_json_error(capsys):
    exit_code = cli.main(["--country-code", "bad_code", "status"])
    assert exit_code == 2

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["error"]["code"] in ("invalid_arguments", "usage_error")
    assert "country_code" in payload["error"]["message"].lower()


def test_service_receives_custom_device_profile(tmp_path: Path):
    import httpx

    from samsung_health_cloud.auth import HealthToken
    from samsung_health_cloud.scsp import CloudToken, ScspIdentity
    from samsung_health_cloud.service import SamsungHealthService
    from samsung_health_cloud.state import StateStore

    captured_profile = []

    class MockScsp(ScspIdentity):
        def __init__(self, client, profile=None):
            super().__init__(client, profile=profile)
            captured_profile.append(self.profile)

        def register(self, **kwargs):
            return "reg-1"

        def issue_token(self, **kwargs):
            return CloudToken("Bearer test-token", 2000000000)

    class MockHealthAuth:
        def issue(self, **kwargs):
            return HealthToken("acc", "ref", "uid-1", 100, 200, "bearer")

    custom_profile = DeviceProfile(
        model_name="SM-CUSTOM99", alias="Special Device", country_code="GBR"
    )
    store = StateStore(tmp_path / "state.json")
    master_file = tmp_path / "master.json"
    master_file.write_text(
        '{"schema":"io.github.charlesbel.samsung-account.master","schema_version":1,"generation":"gen1","created_at":100,"updated_at":100,"account":{"login_id":"u@ex.inv"},"installation":{"physical_address":"addr"},"identity":{"auth_server_url":"https://account.samsung.com","userauth_token":"tok"}}',
        encoding="utf-8",
    )
    master_file.chmod(0o600)

    service = SamsungHealthService(
        store=store,
        master_state_path=master_file,
        health_auth=MockHealthAuth(),
        scsp=MockScsp(httpx.Client(), profile=custom_profile),
    )
    service.initialize()

    assert len(captured_profile) == 1
    assert captured_profile[0].model_name == "SM-CUSTOM99"
    assert captured_profile[0].alias == "Special Device"
    assert captured_profile[0].country_code == "GBR"


def test_public_repo_has_no_hardcoded_specific_samsung_models():
    repo_root = Path(__file__).parent.parent.parent
    forbidden = ["".join(["SM-S", "928B"]), "".join(["SM-S", "938B"])]
    for path in repo_root.rglob("*"):
        if any(
            ignored in path.parts
            for ignored in (
                ".git",
                ".venv",
                ".pytest_cache",
                ".ruff_cache",
                "dist",
                "build",
                ".agy",
            )
        ):
            continue
        if path.is_file() and path.suffix in (
            ".py",
            ".md",
            ".json",
            ".toml",
            ".yml",
            ".yaml",
            ".sh",
        ):
            content = path.read_text(encoding="utf-8", errors="ignore")
            for model in forbidden:
                assert model not in content, f"Found forbidden model {model} in {path}"
