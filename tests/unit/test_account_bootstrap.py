from __future__ import annotations

import base64
import json
import stat
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from samsung_health_cloud import cli
from samsung_health_cloud.account_auth import AccountBootstrap, _validate_response_url
from samsung_health_cloud.capture_redirect import is_expected_redirect_uri
from samsung_health_cloud.capture_redirect import main as capture_main
from samsung_health_cloud.constants import ENTRY_POINT_URL, REDIRECT_URI
from samsung_health_cloud.exceptions import AuthenticationError, SamsungHealthCloudError

FIXTURE = Path(__file__).parents[1] / "contract" / "fixtures" / "master-state-v1.synthetic.json"


def _public_key_b64() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der = private_key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(der).decode()


def _encrypt_callback(value: str, key: str) -> str:
    key_bytes = key.encode()[:16].ljust(16, b"\0")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(value.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key_bytes), modes.ECB()).encryptor()
    return (encryptor.update(padded) + encryptor.finalize()).hex()


def _redirect(state_key: str, *, auth_server: str = "https://synthetic.samsungosp.com") -> str:
    response_key = "response-key-001"
    values = {
        "state": _encrypt_callback(response_key, state_key),
        "auth_server_url": _encrypt_callback(auth_server, response_key),
        "code": _encrypt_callback("synthetic-code", response_key),
        "retValue": _encrypt_callback("synthetic@example.invalid", response_key),
    }
    return f"{REDIRECT_URI}?" + str(httpx.QueryParams(values))


def _entry_response(request: httpx.Request, *, url: str | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "chkDoNum": 1000,
            "pkiPublicKey": _public_key_b64(),
            "signInURI": "https://account.samsung.com/accounts/signInGate",
        },
        request=httpx.Request("GET", url or str(request.url)),
    )


def test_auth_start_uses_exact_entry_point_without_redirect_and_writes_account_pending(
    tmp_path: Path,
):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _entry_response(request)

    master = tmp_path / "samsung-account" / "master.json"
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    auth = AccountBootstrap(master_path=master, client=client)

    login_url = auth.start(country="FR", locale="fr-FR")

    assert [str(req.url) for req in requests] == [ENTRY_POINT_URL]
    query = parse_qs(urlsplit(login_url).query)
    assert query["locale"] == ["fr-FR"]
    assert query["mode"] == ["C"]
    assert query["svcParam"][0] != ""
    pending_path = master.parent / "pending.json"
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    assert set(pending) == {"code_verifier", "created_at", "device_id", "state"}
    assert len(pending["code_verifier"]) == 43
    assert stat.S_IMODE(pending_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(master.parent.stat().st_mode) == 0o700
    assert not (tmp_path / "samsung-find").exists()


def test_auth_start_rejects_hostile_final_entry_response_url(tmp_path: Path):
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://evil.invalid/accounts/ANDROIDSDK/getEntryPoint"),
    )
    with pytest.raises(SamsungHealthCloudError, match="untrusted|URL|authority"):
        _validate_response_url(response, expected_url=ENTRY_POINT_URL, operation="entry point")


def test_auth_start_rejects_hostile_redirect_without_following_it(tmp_path: Path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302, headers={"location": "https://evil.invalid/steal"}, request=request
        )

    auth = AccountBootstrap(
        master_path=tmp_path / "samsung-account" / "master.json",
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
    )
    with pytest.raises(SamsungHealthCloudError, match="redirect"):
        auth.start()
    assert len(requests) == 1


def test_auth_complete_writes_only_private_neutral_master_with_fixture_schema(
    tmp_path: Path, monkeypatch
):
    master = tmp_path / "samsung-account" / "master.json"
    pending = master.parent / "pending.json"
    pending.parent.mkdir(mode=0o700)
    pending.write_text(
        json.dumps(
            {
                "state": "pending-state-001",
                "code_verifier": "v" * 43,
                "device_id": "synthetic-device",
                "created_at": 1000,
            }
        ),
        encoding="utf-8",
    )
    pending.chmod(0o600)
    monkeypatch.setattr("samsung_health_cloud.account_auth.time.time", lambda: 1001)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={"userauth_token": "synthetic-master-token", "userId": "synthetic-user-id"},
            request=request,
        )

    auth = AccountBootstrap(
        master_path=master, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    status = auth.complete(_redirect("pending-state-001"))

    assert status == {
        "authenticated": True,
        "device_id_present": True,
        "schema_version": 1,
        "user_id_present": True,
    }
    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert str(seen[0].url) == "https://synthetic.samsungosp.com/auth/oauth2/authenticate"
    payload = json.loads(master.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload.keys() == fixture.keys()
    assert payload["account"].keys() == fixture["account"].keys()
    assert payload["installation"].keys() == fixture["installation"].keys()
    assert payload["identity"].keys() == fixture["identity"].keys()
    assert payload["schema"] == fixture["schema"]
    assert payload["schema_version"] == fixture["schema_version"]
    assert stat.S_IMODE(master.stat().st_mode) == 0o600
    assert not pending.exists()
    assert not (tmp_path / "samsung-find").exists()


def test_auth_complete_rejects_secret_post_redirect_and_does_not_write_master(
    tmp_path: Path, monkeypatch
):
    master = tmp_path / "samsung-account" / "master.json"
    pending = master.parent / "pending.json"
    pending.parent.mkdir(mode=0o700)
    pending.write_text(
        json.dumps({"state": "s", "code_verifier": "v" * 43, "device_id": "d", "created_at": 1000}),
        encoding="utf-8",
    )
    pending.chmod(0o600)
    monkeypatch.setattr("samsung_health_cloud.account_auth.time.time", lambda: 1001)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302, headers={"location": "https://evil.invalid/steal"}, request=request
        )

    auth = AccountBootstrap(
        master_path=master, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(SamsungHealthCloudError, match="redirect"):
        auth.complete(_redirect("s"))
    assert not master.exists()


@pytest.mark.parametrize(
    "callback",
    [
        "ms-app://callback?state=x",
        f"{REDIRECT_URI}.evil?state=x",
        REDIRECT_URI.replace("ms-app://", "ms-app://evil@") + "?state=x",
        f"{REDIRECT_URI}/extra?state=x",
    ],
)
def test_callback_target_is_exact(callback: str):
    assert not is_expected_redirect_uri(callback)


def test_expired_pending_is_deleted_before_network(tmp_path: Path, monkeypatch):
    master = tmp_path / "samsung-account" / "master.json"
    pending = master.parent / "pending.json"
    pending.parent.mkdir(mode=0o700)
    pending.write_text(
        json.dumps({"state": "s", "code_verifier": "v" * 43, "device_id": "d", "created_at": 1000}),
        encoding="utf-8",
    )
    pending.chmod(0o600)
    monkeypatch.setattr("samsung_health_cloud.account_auth.time.time", lambda: 1901)

    auth = AccountBootstrap(
        master_path=master,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: pytest.fail("network called"))
        ),
    )
    with pytest.raises(AuthenticationError, match="expired"):
        auth.complete(f"{REDIRECT_URI}?state=x")
    assert not pending.exists()


def test_capture_redirect_writes_private_account_file_and_rejects_wrong_callback(
    tmp_path: Path, monkeypatch
):
    target = tmp_path / "samsung-account" / "redirect.uri"
    monkeypatch.setenv("SAMSUNG_ACCOUNT_REDIRECT_PATH", str(target))
    good = f"{REDIRECT_URI}?state=synthetic"

    assert capture_main(["capture_redirect", good]) == 0
    assert target.read_text(encoding="utf-8") == good
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    target.unlink()
    assert capture_main(["capture_redirect", "ms-app://wrong?state=synthetic"]) == 2
    assert not target.exists()


def test_account_status_is_non_secret(tmp_path: Path):
    master = tmp_path / "samsung-account" / "master.json"
    master.parent.mkdir(mode=0o700)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    master.write_text(json.dumps(fixture), encoding="utf-8")
    master.chmod(0o600)

    status = AccountBootstrap(master_path=master, client=httpx.Client()).public_status()

    rendered = json.dumps(status)
    assert status["authenticated"] is True
    assert "synthetic-test-master-token-not-real" not in rendered
    assert "synthetic-test-user@example.invalid" not in rendered
    assert "synthetic-test-user-id" not in rendered


def test_health_cli_exposes_independent_account_bootstrap_commands():
    parser = cli.build_parser()
    for argv, command in (
        (["install-handler"], "install-handler"),
        (["auth-start", "--country", "fr", "--locale", "fr-FR"], "auth-start"),
        (["auth-complete"], "auth-complete"),
        (["account-status"], "account-status"),
    ):
        assert parser.parse_args(argv).command == command


def test_cli_account_status_emits_non_secret_envelope(tmp_path: Path, capsys):
    master = tmp_path / "samsung-account" / "master.json"
    master.parent.mkdir(mode=0o700)
    master.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    master.chmod(0o600)

    assert cli.main(["--master-state", str(master), "account-status"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["data"]["authenticated"] is True
    assert "synthetic-test-master-token-not-real" not in output
    assert "synthetic-test-user@example.invalid" not in output


def test_cli_auth_complete_consumes_redirect_before_validation(tmp_path: Path, capsys):
    master = tmp_path / "samsung-account" / "master.json"
    redirect = master.parent / "redirect.uri"
    redirect.parent.mkdir(mode=0o700)
    redirect.write_text("ms-app://wrong?state=synthetic", encoding="utf-8")
    redirect.chmod(0o600)

    assert cli.main(["--master-state", str(master), "auth-complete"]) == 3
    capsys.readouterr()
    assert not redirect.exists()


def test_install_handler_targets_health_capture_module(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/xdg-mime")
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> None:
        calls.append(command)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    master = tmp_path / ".config" / "samsung-account" / "master.json"

    result = cli.install_account_handler(master)

    desktop = Path(str(result["handler"]))
    content = desktop.read_text(encoding="utf-8")
    assert "-m samsung_health_cloud.capture_redirect %u" in content
    assert "SAMSUNG_ACCOUNT_REDIRECT_PATH=" in content
    assert "samsung_find" not in content
    assert calls == [
        [
            "/usr/bin/xdg-mime",
            "default",
            desktop.name,
            "x-scheme-handler/ms-app",
        ]
    ]
