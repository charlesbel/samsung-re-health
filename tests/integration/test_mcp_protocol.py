from pathlib import Path

from samsung_health_cloud import HealthConfig
from samsung_health_cloud.mcp_server import create_mcp_server, invoke_tool


def test_mcp_protocol_direct_call_policy(tmp_path: Path):
    config = HealthConfig(cache_path=tmp_path / "empty.sqlite3")
    server = create_mcp_server(config=config, allow_records=False, allow_sync=False)

    # 1. Test status call without network auth initialization
    status_res = invoke_tool(server, "samsung_health_status", {})
    assert status_res["ok"] is True
    assert "health_access_token_present" in status_res["data"]

    # 2. Test types call
    types_res = invoke_tool(server, "samsung_health_types", {})
    assert types_res["ok"] is True
    assert isinstance(types_res["data"], list)
    assert len(types_res["data"]) >= 10

    # 3. Test input parameter validation on bounds/lengths
    bad_res = invoke_tool(server, "samsung_health_analyze", {"health_type": "a" * 200})
    assert bad_res["ok"] is False
    assert bad_res["error"]["code"] == "usage_error"
