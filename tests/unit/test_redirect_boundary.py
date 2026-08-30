from __future__ import annotations

import httpx
import pytest

from samsung_health_cloud.auth import (
    HealthAuth,
    SamsungHealthCloudError,
    _validate_response_url,
    safe_http_call,
)
from samsung_health_cloud.data import CloudDataClient
from samsung_health_cloud.models import DeviceProfile
from samsung_health_cloud.scsp import ScspIdentity


def test_auth_authorize_redirect_fails_closed_without_replaying_to_hostile_host() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.host == "evil.attacker.com":
            return httpx.Response(
                200,
                json={"code": "attacker-code", "auth_data": {"userId": "attacker-user"}},
            )
        if request.url.path == "/auth/oauth2/v2/authorize":
            return httpx.Response(
                302,
                headers={"Location": "https://evil.attacker.com/steal_code"},
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        auth = HealthAuth(client)
        with pytest.raises(
            SamsungHealthCloudError,
            match="redirect not allowed|network request failed|failed with HTTP",
        ):
            auth.issue(
                auth_server_url="https://eu-auth2.samsungosp.com",
                master_token="synthetic-master-token",
                login_id="victim@example.com",
                verifier="fixed-verifier",
                physical_address="fixed-address",
            )

    assert len(recorded_requests) == 1
    assert recorded_requests[0].url.host == "eu-auth2.samsungosp.com"
    assert not any(req.url.host == "evil.attacker.com" for req in recorded_requests)


def test_auth_token_redirect_fails_closed_without_replaying_to_hostile_host() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.host == "evil.attacker.com":
            return httpx.Response(
                200,
                json={
                    "access_token": "attacker-access-token",
                    "refresh_token": "attacker-refresh-token",
                    "expires_in": 3600,
                    "refresh_token_expires_in": 7200,
                },
            )
        if request.url.path == "/auth/oauth2/v2/authorize":
            return httpx.Response(
                200,
                json={"code": "legit-code", "auth_data": {"userId": "legit-user"}},
            )
        if request.url.path == "/auth/oauth2/token":
            return httpx.Response(
                307,
                headers={"Location": "https://evil.attacker.com/steal_token"},
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        auth = HealthAuth(client)
        with pytest.raises(
            SamsungHealthCloudError,
            match="redirect not allowed|network request failed|failed with HTTP",
        ):
            auth.issue(
                auth_server_url="https://eu-auth2.samsungosp.com",
                master_token="synthetic-master-token",
                login_id="victim@example.com",
                verifier="fixed-verifier",
                physical_address="fixed-address",
            )

    assert len(recorded_requests) == 2
    assert all(req.url.host == "eu-auth2.samsungosp.com" for req in recorded_requests)
    assert not any(req.url.host == "evil.attacker.com" for req in recorded_requests)


def test_scsp_register_redirect_fails_closed() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.host == "evil.attacker.com":
            return httpx.Response(200, json={"registrationId": "attacker-registration-id"})
        if request.url.path.endswith("/register"):
            return httpx.Response(
                307,
                headers={"Location": "https://evil.attacker.com/register"},
            )
        return httpx.Response(404)

    profile = DeviceProfile(model_name="SM-TEST", alias="Test", country_code="USA")
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        scsp = ScspIdentity(client, profile=profile)
        with pytest.raises(
            SamsungHealthCloudError,
            match="redirect not allowed|network request failed|failed with HTTP",
        ):
            scsp.register(
                health_access_token="test-token",
                user_id="test-uid",
                cdid="test-cdid",
            )

    assert len(recorded_requests) == 1
    assert recorded_requests[0].url.host == "play.samsungcloud.com"
    assert not any(req.url.host == "evil.attacker.com" for req in recorded_requests)


def test_scsp_token_redirect_fails_closed() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.host == "evil.attacker.com":
            return httpx.Response(
                200,
                json={
                    "tokenType": "Bearer",
                    "accessToken": "attacker-cloud-token",
                    "expiresAt": 9999999999,
                },
            )
        if request.url.path.endswith("/tokens"):
            return httpx.Response(
                308,
                headers={"Location": "https://evil.attacker.com/tokens"},
            )
        return httpx.Response(404)

    profile = DeviceProfile(model_name="SM-TEST", alias="Test", country_code="USA")
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        scsp = ScspIdentity(client, profile=profile)
        with pytest.raises(
            SamsungHealthCloudError,
            match="redirect not allowed|network request failed|failed with HTTP",
        ):
            scsp.issue_token(
                health_access_token="test-token",
                user_id="test-uid",
                cdid="test-cdid",
            )

    assert len(recorded_requests) == 1
    assert recorded_requests[0].url.host == "play.samsungcloud.com"
    assert not any(req.url.host == "evil.attacker.com" for req in recorded_requests)


def test_cloud_data_client_redirect_fails_closed() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.host == "evil.attacker.com":
            return httpx.Response(
                200,
                json={"documents": [{"data": {"fake": "stolen"}}], "hasNext": False},
            )
        if "/documents" in request.url.path:
            return httpx.Response(
                302,
                headers={"Location": "https://evil.attacker.com/fake_docs"},
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        data_client = CloudDataClient(client)
        with pytest.raises(
            SamsungHealthCloudError,
            match="redirect not allowed|network request failed|failed with HTTP",
        ):
            data_client.list_documents(
                manifest_id="com.samsung.health.sleep",
                schema_revision=18,
                cloud_authorization="Bearer test-cloud-auth",
            )

    assert len(recorded_requests) == 1
    assert recorded_requests[0].url.host == "api.samsungcloud.com"
    assert not any(req.url.host == "evil.attacker.com" for req in recorded_requests)


def test_response_with_synthetic_redirect_history_is_rejected() -> None:
    hist_resp = httpx.Response(
        302, request=httpx.Request("GET", "https://api.samsungcloud.com/test")
    )
    final_resp = httpx.Response(
        200,
        request=httpx.Request("GET", "https://evil.attacker.com/test"),
        history=[hist_resp],
        json={"data": "evil"},
    )

    with pytest.raises(SamsungHealthCloudError, match="redirect not allowed"):
        safe_http_call("test_op", lambda: final_resp)


def test_validate_response_url_rejects_userinfo_query_and_fragment() -> None:
    urls = (
        "https://user:pass@account.samsung.com/auth/oauth2/token",
        "https://account.samsung.com/auth/oauth2/token?hostile=1",
        "https://account.samsung.com/auth/oauth2/token#hostile",
    )
    for url in urls:
        response = httpx.Response(200, request=httpx.Request("GET", url))
        with pytest.raises(SamsungHealthCloudError, match="userinfo|query mismatch|fragment"):
            _validate_response_url(
                response,
                expected_host="account.samsung.com",
                expected_path="/auth/oauth2/token",
                operation="token",
            )


def test_validate_response_url_rejects_untrusted_scheme_host_port_path() -> None:
    # Wrong scheme (http)
    req = httpx.Request("GET", "http://account.samsung.com/auth/oauth2/token")
    resp = httpx.Response(200, request=req)
    with pytest.raises(SamsungHealthCloudError, match="untrusted|scheme|authority"):
        _validate_response_url(
            resp,
            expected_host="account.samsung.com",
            expected_path="/auth/oauth2/token",
            operation="token",
        )

    # Wrong host (evil domain)
    req = httpx.Request("GET", "https://evil-samsungosp.com/auth/oauth2/token")
    resp = httpx.Response(200, request=req)
    with pytest.raises(SamsungHealthCloudError, match="untrusted|authority"):
        _validate_response_url(
            resp,
            expected_host="samsungosp.com",
            expected_path="/auth/oauth2/token",
            operation="token",
        )

    # Wrong port
    req = httpx.Request("GET", "https://account.samsung.com:8443/auth/oauth2/token")
    resp = httpx.Response(200, request=req)
    with pytest.raises(SamsungHealthCloudError, match="port"):
        _validate_response_url(
            resp,
            expected_host="account.samsung.com",
            expected_path="/auth/oauth2/token",
            operation="token",
        )

    # Wrong path
    req = httpx.Request("GET", "https://account.samsung.com/attacker/oauth2/token")
    resp = httpx.Response(200, request=req)
    with pytest.raises(SamsungHealthCloudError, match="path"):
        _validate_response_url(
            resp,
            expected_host="account.samsung.com",
            expected_path="/auth/oauth2/token",
            operation="token",
        )
