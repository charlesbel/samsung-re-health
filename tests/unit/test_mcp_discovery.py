from samsung_health_cloud.mcp_server import create_mcp_server, list_registered_tools


def test_mcp_tool_discovery_contains_default_and_gated_tools():
    server = create_mcp_server()
    tools = list_registered_tools(server)
    tool_names = {t["name"] for t in tools}

    # Core read-only tools
    assert "samsung_health_status" in tool_names
    assert "samsung_health_types" in tool_names
    assert "samsung_health_inventory" in tool_names
    assert "samsung_health_analyze" in tool_names
    assert "samsung_health_summary" in tool_names
    assert "samsung_health_cache_status" in tool_names

    # Sensitive/gated tools
    assert "samsung_health_read_records" in tool_names
    assert "samsung_health_sync" in tool_names

    for tool in tools:
        assert tool["description"]
        assert len(tool["description"]) > 10
        # No medical overclaims in descriptions
        assert "diagnos" not in tool["description"].lower()
        assert "prescrib" not in tool["description"].lower()
