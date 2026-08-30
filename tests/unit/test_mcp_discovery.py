from samsung_health_cloud.mcp_server import (
    create_mcp_server,
    invoke_tool,
    list_registered_tools,
)


def test_mcp_default_tool_discovery_contains_only_six_safe_tools():
    # Defaults must be allow_records=False, allow_sync=False
    server = create_mcp_server()
    tools = list_registered_tools(server)
    tool_names = {t["name"] for t in tools}

    assert tool_names == {
        "samsung_health_status",
        "samsung_health_types",
        "samsung_health_inventory",
        "samsung_health_analyze",
        "samsung_health_summary",
        "samsung_health_cache_status",
    }
    assert len(tools) == 6

    # Gated tools are not in default discovery
    assert "samsung_health_read_records" not in tool_names
    assert "samsung_health_sync" not in tool_names

    for tool in tools:
        assert tool["description"]
        assert len(tool["description"]) > 10
        # No medical overclaims
        assert "diagnos" not in tool["description"].lower()
        assert "prescrib" not in tool["description"].lower()


def test_mcp_opt_in_tools_discovery():
    server = create_mcp_server(allow_records=True, allow_sync=True)
    tools = list_registered_tools(server)
    tool_names = {t["name"] for t in tools}

    assert "samsung_health_read_records" in tool_names
    assert "samsung_health_sync" in tool_names
    assert len(tools) == 8


def test_mcp_calling_disabled_tool_returns_error_envelope():
    server = create_mcp_server(allow_records=False)
    res = invoke_tool(server, "samsung_health_read_records", {"manifest_id": "sleep"})
    assert res["ok"] is False
    assert res["error"]["code"] == "tool_not_found"
