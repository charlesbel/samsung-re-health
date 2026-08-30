import httpx
import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.data import CloudDataClient


def test_list_documents_is_a_bounded_get_with_cloud_auth():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/data/v3/com.samsung.health.step_count/documents"
        assert request.url.params["schemaRevision"] == "17"
        assert request.url.params["limit"] == "1"
        assert request.url.params["start_time"] == "1000"
        assert request.url.params["end_time"] == "2000"
        assert request.headers["authorization"] == "Bearer cloud-secret"
        assert request.headers["x-sc-e2ee-state"] == "OFF"
        return httpx.Response(200, json={"items": [{"uuid": "record-1"}], "pageToken": "next"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = CloudDataClient(client).list_documents(
            manifest_id="com.samsung.health.step_count",
            schema_revision=17,
            cloud_authorization="Bearer cloud-secret",
            limit=1,
            start_time=1000,
            end_time=2000,
        )

    assert payload["items"][0]["uuid"] == "record-1"


def test_iter_documents_follows_all_pages_and_detects_pagination_loops():
    requested_tokens = []

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        requested_tokens.append(token)
        pages = {
            None: {
                "documents": [{"data": {"count": 1}}],
                "hasNext": True,
                "nextPageToken": "p2",
            },
            "p2": {
                "documents": [{"data": {"count": 2}}],
                "hasNext": True,
                "nextPageToken": "p3",
            },
            "p3": {
                "documents": [{"data": {"count": 3}}],
                "hasNext": False,
                "nextPageToken": "",
            },
        }
        return httpx.Response(200, json=pages[token])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records = list(
            CloudDataClient(client).iter_documents(
                manifest_id="com.samsung.health.step_count",
                schema_revision=5,
                cloud_authorization="Bearer cloud-secret",
                page_size=2,
            )
        )
    assert [record["data"]["count"] for record in records] == [1, 2, 3]
    assert requested_tokens == [None, "p2", "p3"]

    def looping_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"documents": [], "hasNext": True, "nextPageToken": "same"},
        )

    with (
        httpx.Client(transport=httpx.MockTransport(looping_handler)) as client,
        pytest.raises(SamsungHealthCloudError, match="pagination loop"),
    ):
        pages = CloudDataClient(client).iter_pages(
            manifest_id="com.samsung.health.sleep",
            schema_revision=18,
            cloud_authorization="Bearer cloud-secret",
            start_page_token="same",
        )
        next(pages)


def test_list_documents_rejects_unsafe_manifest_and_large_limit():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as client:
        data = CloudDataClient(client)
        for manifest_id, limit in (
            ("../tokens", 1),
            ("com.samsung.health.step_count", 1001),
        ):
            try:
                data.list_documents(
                    manifest_id=manifest_id,
                    schema_revision=1,
                    cloud_authorization="Bearer secret",
                    limit=limit,
                )
            except ValueError as exc:
                assert "secret" not in str(exc)
            else:
                raise AssertionError("unsafe request was accepted")
