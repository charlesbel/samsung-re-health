import json

import pytest

from samsung_health_cloud.auth import SamsungHealthCloudError
from samsung_health_cloud.catalog import ManifestInfo
from samsung_health_cloud.exporter import JsonlExporter


class InterruptingDataClient:
    def __init__(self):
        self.start_tokens = []

    def iter_pages(self, **kwargs):
        self.start_tokens.append(kwargs["start_page_token"])
        yield {
            "documents": [{"data": {"count": 1}}],
            "hasNext": True,
            "nextPageToken": "p2",
        }
        raise RuntimeError("simulated interruption")


class ResumingDataClient:
    def __init__(self):
        self.start_tokens = []

    def iter_pages(self, **kwargs):
        self.start_tokens.append(kwargs["start_page_token"])
        yield {
            "documents": [{"data": {"count": 2}}],
            "hasNext": False,
            "nextPageToken": "",
        }


def test_jsonl_export_resumes_after_a_page_without_duplicates(tmp_path):
    manifest = ManifestInfo("com.samsung.health.step_count", 5, 6)
    output = tmp_path / "steps.jsonl"
    first = InterruptingDataClient()
    exporter = JsonlExporter()

    with pytest.raises(RuntimeError, match="interruption"):
        exporter.export_manifest(
            data_client=first,
            manifest=manifest,
            cloud_authorization="Bearer secret",
            output_path=output,
            page_size=200,
        )

    assert first.start_tokens == [None]
    assert not output.exists()
    assert (tmp_path / "steps.jsonl.pages" / "00000000.jsonl").exists()

    second = ResumingDataClient()
    result = exporter.export_manifest(
        data_client=second,
        manifest=manifest,
        cloud_authorization="Bearer secret",
        output_path=output,
        page_size=200,
    )

    assert second.start_tokens == ["p2"]
    assert result.record_count == 2
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [item["data"]["count"] for item in records] == [1, 2]
    state_text = (tmp_path / "steps.jsonl.pages" / "state.json").read_text()
    assert "Bearer secret" not in state_text

    output.unlink()

    class NetworkMustNotBeCalled:
        def iter_pages(self, **kwargs):
            raise AssertionError("network must not be called for local reassembly")

    rebuilt = exporter.export_manifest(
        data_client=NetworkMustNotBeCalled(),
        manifest=manifest,
        cloud_authorization="Bearer another-secret",
        output_path=output,
        page_size=200,
    )
    assert rebuilt.record_count == 2
    assert output.exists()
    expected_records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [record["data"]["count"] for record in expected_records] == [1, 2]

    with pytest.raises(SamsungHealthCloudError, match="checkpoint"):
        exporter.export_manifest(
            data_client=NetworkMustNotBeCalled(),
            manifest=manifest,
            cloud_authorization="Bearer another-secret",
            output_path=output,
            page_size=100,
        )

    output.write_text("truncated\n")
    exporter.export_manifest(
        data_client=NetworkMustNotBeCalled(),
        manifest=manifest,
        cloud_authorization="Bearer another-secret",
        output_path=output,
        page_size=200,
    )
    assert [json.loads(line) for line in output.read_text().splitlines()] == expected_records

    extra_page = tmp_path / "steps.jsonl.pages" / "99999999.jsonl"
    extra_page.write_text("{}\n")
    with pytest.raises(SamsungHealthCloudError, match="unexpected export page"):
        exporter.export_manifest(
            data_client=NetworkMustNotBeCalled(),
            manifest=manifest,
            cloud_authorization="Bearer another-secret",
            output_path=output,
            page_size=200,
        )
