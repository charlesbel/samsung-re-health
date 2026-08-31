from pathlib import Path

from samsung_health_cloud import HealthConfig
from samsung_health_cloud.mcp_server import (
    create_mcp_server,
    invoke_tool,
    list_registered_tools,
)
from samsung_health_cloud.serialization import redact_raw_records


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
    assert bad_res["error"]["code"] in ("invalid_arguments", "usage_error")


def test_mcp_schemas_annotations_and_direct_validation_are_exact(tmp_path: Path):
    server = create_mcp_server(
        config=HealthConfig(cache_path=tmp_path / "empty.sqlite3"),
        allow_records=True,
        allow_sync=True,
    )
    tools = list_registered_tools(server)
    assert tools
    for tool in tools:
        assert tool["inputSchema"]["additionalProperties"] is False
        is_sync = tool["name"] == "samsung_health_sync"
        assert tool["annotations"] == {
            "readOnlyHint": not is_sync,
            "destructiveHint": False,
            "idempotentHint": not is_sync,
            "openWorldHint": is_sync,
        }

    wrong_type = invoke_tool(
        server,
        "samsung_health_read_records",
        {"manifest_id": "sleep", "limit": True},
    )
    assert wrong_type["ok"] is False
    assert wrong_type["error"]["code"] == "invalid_arguments"
    unknown = invoke_tool(server, "samsung_health_status", {"unexpected": 1})
    assert unknown["ok"] is False
    assert unknown["error"]["code"] == "invalid_arguments"


def test_raw_record_redaction_is_explicit_allowlist_and_fail_closed():
    [record] = redact_raw_records(
        [
            {
                "step_count": 12,
                "stage": "REM",
                "datauuid": "record-id",
                "latitude": 48.8,
                "url": "https://example.invalid/private",
                "path": "/private/file",
                "hardware": "device-model",
                "unknown_note": "private free text",
                "unknown_number": 42,
            }
        ]
    )
    assert record["step_count"] == 12
    assert record["stage"] == "REM"
    assert set(record) == {
        "step_count",
        "stage",
        "datauuid",
        "latitude",
        "url",
        "path",
        "hardware",
        "unknown_note",
        "unknown_number",
    }
    assert all(
        value == "[REDACTED]" for key, value in record.items() if key not in {"step_count", "stage"}
    )


def test_mcp_call_tool_result_structured_content_contract(tmp_path: Path):
    import json

    from mcp.types import CallToolResult, TextContent

    config = HealthConfig(cache_path=tmp_path / "empty.sqlite3")
    server = create_mcp_server(config=config)

    # 1. Test dict payload (status)
    status_res = invoke_tool(server, "samsung_health_status", {})
    payload_status = status_res.get("data") if status_res["ok"] else status_res["error"]
    res_status = CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload_status, sort_keys=True))],
        structuredContent=payload_status if isinstance(payload_status, dict) else None,
        isError=not status_res["ok"],
    )
    assert res_status.isError is False
    assert isinstance(res_status.structuredContent, dict)

    # 2. Test list payload (types) - must not crash with Pydantic validation error
    types_res = invoke_tool(server, "samsung_health_types", {})
    payload_types = types_res.get("data") if types_res["ok"] else types_res["error"]
    assert isinstance(payload_types, list)
    res_types = CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload_types, sort_keys=True))],
        structuredContent=payload_types if isinstance(payload_types, dict) else None,
        isError=not types_res["ok"],
    )
    assert res_types.isError is False
    assert res_types.structuredContent is None


def test_mcp_stdio_handshake_synthetic_home(tmp_path: Path):
    import json
    import os
    import subprocess
    import sys

    synthetic_home = tmp_path / "synthetic_home"
    synthetic_home.mkdir(mode=0o700)
    smoke_env = {
        **os.environ,
        "HOME": str(synthetic_home),
        "XDG_CONFIG_HOME": str(synthetic_home / ".config"),
        "XDG_DATA_HOME": str(synthetic_home / ".local" / "share"),
        "XDG_STATE_HOME": str(synthetic_home / ".local" / "state"),
    }

    proc = subprocess.Popen(
        [sys.executable, "-m", "samsung_health_cloud.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=smoke_env,
    )

    try:
        # Initialize
        proc.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test-stdio", "version": "1.0"},
                    },
                }
            )
            + "\n"
        )
        proc.stdin.flush()
        init_resp = json.loads(proc.stdout.readline())
        assert init_resp["result"]["serverInfo"]["name"] == "samsung-re-health"
        assert init_resp["result"]["serverInfo"]["version"] == "0.7.1"

        # Notification
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proc.stdin.flush()

        # Tools list
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
        )
        proc.stdin.flush()
        tools_resp = json.loads(proc.stdout.readline())
        tools = tools_resp["result"]["tools"]
        assert len(tools) == 6
        for t in tools:
            assert t["inputSchema"]["additionalProperties"] is False
            assert t["annotations"]["readOnlyHint"] is True
            assert t["annotations"]["destructiveHint"] is False
            assert t["annotations"]["idempotentHint"] is True
            assert t["annotations"]["openWorldHint"] is False

        # Tools call: types
        proc.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "samsung_health_types", "arguments": {}},
                }
            )
            + "\n"
        )
        proc.stdin.flush()
        types_resp = json.loads(proc.stdout.readline())
        assert types_resp["result"]["isError"] is False
        types_list = json.loads(types_resp["result"]["content"][0]["text"])
        assert len(types_list) >= 10

        # Tools call: invalid argument
        proc.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "samsung_health_status",
                        "arguments": {"invalid_extra": 1},
                    },
                }
            )
            + "\n"
        )
        proc.stdin.flush()
        bad_resp = json.loads(proc.stdout.readline())
        assert bad_resp["result"]["isError"] is True

    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
