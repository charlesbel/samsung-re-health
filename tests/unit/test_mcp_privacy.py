from pathlib import Path

from samsung_health_cloud import HealthConfig
from samsung_health_cloud.cache import HealthCache
from samsung_health_cloud.mcp_server import create_mcp_server, invoke_tool


def test_mcp_read_records_enforces_hard_limit(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    cache = HealthCache(db_path)
    # Insert 100 records
    docs = [
        {
            "data": {
                "datauuid": f"rec-{i}",
                "start_time": 1700000000000 + i * 1000,
                "weight": 70.0 + i * 0.1,
                "private_note": "secret-text",
            },
            "files": [],
            "downloadUrls": [f"https://signed-url.example.com/{i}"],
            "needToDecrypt": False,
        }
        for i in range(100)
    ]
    cache.upsert_documents("com.samsung.health.weight", docs)

    config = HealthConfig(cache_path=db_path)
    server = create_mcp_server(config=config, allow_records=True)

    # Values outside the advertised schema fail closed instead of being coerced.
    result = invoke_tool(
        server, "samsung_health_read_records", {"manifest_id": "weight", "limit": 1000}
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"

    result = invoke_tool(
        server, "samsung_health_read_records", {"manifest_id": "weight", "limit": 50}
    )
    assert result["ok"] is True
    records = result["data"]["records"]
    assert len(records) <= 50

    # Ensure secrets/tokens/signed URLs in payload are redacted
    for record in records:
        assert "secret-text" not in str(record)
        assert "https://signed-url.example.com" not in str(record)


def test_mcp_error_handling_does_not_leak_secrets():
    server = create_mcp_server()
    # Malformed manifest query
    result = invoke_tool(server, "samsung_health_inventory", {"manifest_id": "../../bad_path"})
    assert result["ok"] is False
    assert "error" in result
    assert "code" in result["error"]
    assert "message" in result["error"]
