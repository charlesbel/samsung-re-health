import httpx
import pytest

from samsung_health_cloud.auth import HealthAuth
from samsung_health_cloud.data import CloudDataClient
from samsung_health_cloud.exceptions import SamsungHealthCloudError


def test_data_client_only_issues_get_requests():
    seen_methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_methods.append(request.method)
        assert request.url.host.endswith("samsungcloud.com")
        assert request.method == "GET"
        return httpx.Response(200, json={"documents": [], "nextPageToken": None})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        data_client = CloudDataClient(client)

        for forbidden in (
            "create",
            "write",
            "post",
            "put",
            "delete",
            "patch",
            "upload",
            "update",
        ):
            assert not hasattr(data_client, forbidden), (
                f"CloudDataClient must not have {forbidden} method"
            )

        res = data_client.list_documents(
            manifest_id="com.samsung.health.sleep",
            schema_revision=18,
            cloud_authorization="Bearer test-token",
        )
        assert res == {"documents": [], "nextPageToken": None}
        assert seen_methods == ["GET"]


def test_data_client_rejects_untrusted_host():
    with (
        httpx.Client() as client,
        pytest.raises(SamsungHealthCloudError, match="untrusted host"),
    ):
        CloudDataClient(client, base_url="https://attacker.com")


def test_auth_client_rejects_untrusted_auth_server():
    with (
        httpx.Client() as client,
        pytest.raises(SamsungHealthCloudError, match="authority|domain|untrusted"),
    ):
        auth_client = HealthAuth(client)
        auth_client.issue(
            auth_server_url="https://attacker.com",
            master_token="test-token",
            login_id="user@example.com",
            physical_address="test-addr",
        )
