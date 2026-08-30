from pathlib import Path

from samsung_health_cloud import HealthConfig
from samsung_health_cloud.cache import HealthCache
from samsung_health_cloud.mcp_server import create_mcp_server, invoke_tool


def test_mcp_analyze_tool_against_local_cache(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    cache = HealthCache(db_path)
    cache.upsert_documents(
        "com.samsung.health.sleep",
        [
            {
                "data": {
                    "datauuid": "sleep-1",
                    "start_time": 1700000000000,
                    "end_time": 1700028800000,
                    "efficiency": 85,
                },
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )
    config = HealthConfig(cache_path=db_path)
    server = create_mcp_server(config=config)

    res = invoke_tool(
        server, "samsung_health_analyze", {"health_type": "sleep", "latest": True}
    )
    assert res["ok"] is True
    assert res["data"]["available"] is True
    assert res["data"]["reported_efficiency_percent"] == 85
    assert "calculations" in res["data"]


def test_mcp_types_and_status_tools(tmp_path: Path):
    config = HealthConfig(cache_path=tmp_path / "empty.sqlite3")
    server = create_mcp_server(config=config)

    types_res = invoke_tool(server, "samsung_health_types", {})
    assert types_res["ok"] is True
    assert len(types_res["data"]) >= 10

    status_res = invoke_tool(server, "samsung_health_cache_status", {})
    assert status_res["ok"] is True
    assert "records" in status_res["data"]
