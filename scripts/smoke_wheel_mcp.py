#!/usr/bin/env python3
"""Installed-wheel MCP stdio protocol smoke test with synthetic isolated environment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _send_json(proc: subprocess.Popen, msg: dict) -> None:
    assert proc.stdin is not None
    payload = json.dumps(msg) + "\n"
    proc.stdin.write(payload)
    proc.stdin.flush()


def _recv_json(proc: subprocess.Popen, timeout: float = 5.0) -> dict:
    assert proc.stdout is not None
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if line:
            return json.loads(line.strip())
        time.sleep(0.05)
    raise TimeoutError("timed out waiting for MCP server JSON-RPC response")


def smoke_mcp_server(executable: list[str], env: dict[str, str], *, opt_ins: bool = False) -> None:
    cmd = list(executable)
    if opt_ins:
        cmd.extend(["--allow-records", "--allow-sync"])

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # 1. Initialize protocol handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wheel-smoke-client", "version": "1.0.0"},
            },
        }
        _send_json(proc, init_req)
        init_resp = _recv_json(proc)
        assert init_resp.get("jsonrpc") == "2.0", f"invalid jsonrpc: {init_resp}"
        assert init_resp.get("id") == 1, f"invalid id: {init_resp}"
        result = init_resp.get("result", {})
        assert result.get("serverInfo", {}).get("name") == "samsung-re-health"
        assert result.get("serverInfo", {}).get("version") == "0.7.2"
        assert "capabilities" in result

        # 2. Notification without response
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        _send_json(proc, notif)
        # Verify no immediate response is emitted for a notification

        # 3. List tools
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        _send_json(proc, tools_req)
        tools_resp = _recv_json(proc)
        assert tools_resp.get("id") == 2, f"invalid tools response id: {tools_resp}"
        tools = tools_resp.get("result", {}).get("tools", [])
        expected_count = 8 if opt_ins else 6
        assert len(tools) == expected_count, (
            f"expected {expected_count} tools, found {len(tools)}: {[t['name'] for t in tools]}"
        )

        # Verify closed schemas and annotations
        tool_names = {t["name"] for t in tools}
        assert "samsung_health_status" in tool_names
        assert "samsung_health_types" in tool_names
        assert "samsung_health_inventory" in tool_names
        assert "samsung_health_analyze" in tool_names
        assert "samsung_health_summary" in tool_names
        assert "samsung_health_cache_status" in tool_names

        if opt_ins:
            assert "samsung_health_read_records" in tool_names
            assert "samsung_health_sync" in tool_names

        for tool in tools:
            schema = tool.get("inputSchema", {})
            assert schema.get("type") == "object", f"tool {tool['name']} schema not object"
            assert schema.get("additionalProperties") is False, (
                f"tool {tool['name']} must have additionalProperties: false"
            )
            annotations = tool.get("annotations", {})
            assert annotations.get("destructiveHint") is False
            if tool["name"] == "samsung_health_sync":
                assert annotations.get("readOnlyHint") is False
                assert annotations.get("idempotentHint") is False
                assert annotations.get("openWorldHint") is True
            else:
                assert annotations.get("readOnlyHint") is True
                assert annotations.get("idempotentHint") is True
                assert annotations.get("openWorldHint") is False

        # 4. Safe tool call: types
        call_types = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "samsung_health_types", "arguments": {}},
        }
        _send_json(proc, call_types)
        types_resp = _recv_json(proc)
        assert types_resp.get("id") == 3
        types_result = types_resp.get("result", {})
        assert types_result.get("isError") is False
        content_text = types_result.get("content", [{}])[0].get("text", "")
        types_list = json.loads(content_text)
        assert isinstance(types_list, list)
        assert len(types_list) >= 10

        # 5. Safe tool call: status
        call_status = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "samsung_health_status", "arguments": {}},
        }
        _send_json(proc, call_status)
        status_resp = _recv_json(proc)
        assert status_resp.get("id") == 4
        status_result = status_resp.get("result", {})
        assert status_result.get("isError") is False
        status_data = json.loads(status_result.get("content", [{}])[0].get("text", "{}"))
        assert "health_access_token_present" in status_data
        assert status_data["health_access_token_present"] is False
        assert status_data["master_state_present"] is False

        # 6. Unknown argument error call
        bad_call = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "samsung_health_status",
                "arguments": {"unexpected_unknown_field": 123},
            },
        }
        _send_json(proc, bad_call)
        bad_resp = _recv_json(proc)
        assert bad_resp.get("id") == 5
        bad_result = bad_resp.get("result", {})
        assert bad_result.get("isError") is True
        err_text = bad_result.get("content", [{}])[0].get("text", "")
        assert any(
            term in err_text.lower()
            for term in (
                "validation",
                "unexpected",
                "additional properties",
                "unknown argument",
                "invalid",
            )
        ), f"unexpected error text: {err_text}"

    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        print("ERROR: No wheel found in dist/. Run 'python -m build' first.", file=sys.stderr)
        return 1

    target_wheel = wheels[0]
    print(f"Testing installed-wheel MCP smoke on: {target_wheel.name}")

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        synthetic_home = temp_dir / "home"
        synthetic_home.mkdir(mode=0o700)
        venv_dir = temp_dir / "venv"
        venv_python = venv_dir / "bin" / "python"

        # Canonical entry points
        canonical_cli = venv_dir / "bin" / "samsung-re-health"
        canonical_mcp = venv_dir / "bin" / "samsung-re-health-mcp"

        # Legacy compatibility entry points
        legacy_cli_1 = venv_dir / "bin" / "samsung-health"
        legacy_cli_2 = venv_dir / "bin" / "samsung-health-cloud"
        legacy_mcp = venv_dir / "bin" / "samsung-health-mcp"

        import shutil

        uv_bin = shutil.which("uv")
        if uv_bin:
            subprocess.run(
                [uv_bin, "venv", "--python", sys.executable, str(venv_dir)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    uv_bin,
                    "pip",
                    "install",
                    f"{target_wheel}[mcp]",
                    "--python",
                    str(venv_python),
                ],
                check=True,
                capture_output=True,
            )
        else:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", f"{target_wheel}[mcp]"],
                check=True,
                capture_output=True,
            )

        smoke_env = {
            "PATH": f"{venv_dir / 'bin'}:{os.environ.get('PATH', '')}",
            "HOME": str(synthetic_home),
            "XDG_CONFIG_HOME": str(synthetic_home / ".config"),
            "XDG_DATA_HOME": str(synthetic_home / ".local" / "share"),
            "XDG_STATE_HOME": str(synthetic_home / ".local" / "state"),
        }

        print("1. Verifying existence of canonical and compatibility entry point binaries...")
        for ep in (canonical_cli, canonical_mcp, legacy_cli_1, legacy_cli_2, legacy_mcp):
            assert ep.exists(), f"Expected entry point binary missing: {ep}"

        print("2. Verifying canonical CLI executable behavior...")
        ver_res = subprocess.run(
            [str(canonical_cli), "--version"],
            capture_output=True,
            text=True,
            env=smoke_env,
            check=True,
        )
        assert "samsung-re-health 0.7.2" in ver_res.stdout
        assert "deprecated" not in ver_res.stderr

        cmd_res = subprocess.run(
            [str(canonical_cli), "types"],
            capture_output=True,
            text=True,
            env=smoke_env,
            check=True,
        )
        assert json.loads(cmd_res.stdout)["ok"] is True
        assert "deprecated" not in cmd_res.stderr

        print("3. Verifying legacy CLI compatibility aliases with deprecation notices...")
        leg1_res = subprocess.run(
            [str(legacy_cli_1), "types"],
            capture_output=True,
            text=True,
            env=smoke_env,
            check=True,
        )
        assert json.loads(leg1_res.stdout)["ok"] is True
        assert (
            "Warning: 'samsung-health' CLI command is deprecated; please use 'samsung-re-health'."
            in leg1_res.stderr
        )

        leg2_res = subprocess.run(
            [str(legacy_cli_2), "types"],
            capture_output=True,
            text=True,
            env=smoke_env,
            check=True,
        )
        assert json.loads(leg2_res.stdout)["ok"] is True
        assert (
            "Warning: 'samsung-health-cloud' CLI command is deprecated; please use 'samsung-re-health'."
            in leg2_res.stderr
        )

        print("4. Running canonical stdio MCP smoke (default 6 tools)...")
        smoke_mcp_server([str(canonical_mcp)], smoke_env, opt_ins=False)

        print("5. Running canonical stdio MCP smoke (opt-in 8 tools)...")
        smoke_mcp_server([str(canonical_mcp)], smoke_env, opt_ins=True)

        print("6. Running legacy stdio MCP smoke alias...")
        smoke_mcp_server([str(legacy_mcp)], smoke_env, opt_ins=False)

    print("SUCCESS: Installed-wheel MCP and CLI entry points smoke completed perfectly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
