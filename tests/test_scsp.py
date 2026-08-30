import json

import httpx

from samsung_health_cloud.scsp import DeviceProfile, ScspIdentity


def test_scsp_registers_without_hardware_id_then_issues_redacted_cloud_token():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-sc-app-id"] == "1y90e30264"
        assert request.headers["x-sc-cdid"] == "stable-cdid"
        assert request.headers["x-sc-access-token"] == "health-secret"
        assert request.headers["x-sc-uid"] == "uid-1"
        assert "x-sc-pdid" not in request.headers
        if request.url.path.endswith("/register"):
            payload = json.loads(request.content)
            assert payload["app"]["version"] == "7.00.6.003"
            assert payload["device"]["modelName"] == "SM-S938B"
            assert payload["device"]["alias"] == "Hermes Read-Only"
            return httpx.Response(200, json={"registrationId": "registration-1"})
        assert request.url.path.endswith("/tokens")
        assert request.headers["x-sc-app-version"] == "7.00.6.003"
        return httpx.Response(
            200,
            json={"tokenType": "Bearer", "accessToken": "cloud-secret", "expiresAt": 2_000_000_000},
        )

    profile = DeviceProfile(model_name="SM-S938B", alias="Hermes Read-Only", country_code="FRA")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        identity = ScspIdentity(client, profile=profile)
        registration_id = identity.register(
            health_access_token="health-secret", user_id="uid-1", cdid="stable-cdid"
        )
        token = identity.issue_token(
            health_access_token="health-secret", user_id="uid-1", cdid="stable-cdid"
        )

    assert registration_id == "registration-1"
    assert token.authorization == "Bearer cloud-secret"
    assert token.expires_at == 2_000_000_000
    assert "cloud-secret" not in repr(token)
    assert [request.url.path for request in requests] == ["/identity/v1/register", "/identity/v1/tokens"]
