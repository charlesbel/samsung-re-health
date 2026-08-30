import httpx
import pytest

from samsung_health_cloud.auth import (
    HEALTH_CLIENT_ID,
    HealthAuth,
    SamsungHealthCloudError,
)


def test_health_auth_uses_pkce_without_scope_and_redacts_tokens():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/auth/oauth2/v2/authorize"
            params = dict(request.url.params)
            seen["authorize"] = params
            assert params["client_id"] == HEALTH_CLIENT_ID
            assert params["response_type"] == "code"
            assert params["userauth_token"] == "master-secret"
            assert "scope" not in params
            return httpx.Response(
                200,
                json={"code": "authorization-code", "auth_data": {"userId": "uid-1"}},
            )
        assert request.url.path == "/auth/oauth2/token"
        form = dict(httpx.QueryParams(request.content.decode()))
        seen["token"] = form
        assert form["client_id"] == HEALTH_CLIENT_ID
        assert form["grant_type"] == "authorization_code"
        assert form["code"] == "authorization-code"
        assert form["code_verifier"] == "fixed-verifier"
        return httpx.Response(
            200,
            json={
                "access_token": "health-secret",
                "refresh_token": "refresh-secret",
                "expires_in": 100,
                "refresh_token_expires_in": 200,
                "token_type": "bearer",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        token = HealthAuth(client).issue(
            auth_server_url="https://eu-auth2.samsungosp.com",
            master_token="master-secret",
            login_id="person@example.com",
            verifier="fixed-verifier",
            physical_address="fixed-physical",
        )

    assert token.user_id == "uid-1"
    assert token.access_token == "health-secret"
    assert token.refresh_token == "refresh-secret"
    assert "health-secret" not in repr(token)
    assert "refresh-secret" not in repr(token)
    assert set(seen) == {"authorize", "token"}


def test_health_auth_detaches_sensitive_httpx_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed {request.url}", request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SamsungHealthCloudError, match="network request failed") as captured,
    ):
        HealthAuth(client).issue(
            auth_server_url="https://eu-auth2.samsungosp.com",
            master_token="master-secret",
            login_id="person@example.com",
            verifier="fixed-verifier",
            physical_address="fixed-physical",
        )
    assert "master-secret" not in str(captured.value)
    assert captured.value.__context__ is None
