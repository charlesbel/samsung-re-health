from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .client import SamsungHealthClient, SamsungHealthLocalClient
from .config import HealthConfig
from .exceptions import SamsungHealthError, UsageError
from .serialization import envelope, error_envelope, redact_secrets

__all__ = [
    "SamsungHealthMcpServer",
    "create_mcp_server",
    "invoke_tool",
    "list_registered_tools",
    "main",
    "run_stdio_server",
]

MAX_RECORD_LIMIT = 50


class SamsungHealthMcpServer:
    """Stdio-based Model Context Protocol (MCP) server for Samsung Health Cloud."""

    def __init__(
        self,
        config: HealthConfig | None = None,
        *,
        allow_records: bool = True,
        allow_sync: bool = True,
    ) -> None:
        self.config = config or HealthConfig()
        self.allow_records = allow_records
        self.allow_sync = allow_sync
        self._tools: dict[str, dict[str, Any]] = {}
        self._register_default_tools()

    def _register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def _register_default_tools(self) -> None:
        # 1. status
        self._register_tool(
            name="samsung_health_status",
            description="Inspect local authentication token presence and expiration timestamps without exposing secrets.",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_status,
        )

        # 2. types
        self._register_tool(
            name="samsung_health_types",
            description="List supported Samsung Health manifest types and schema revision metadata.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional type name, alias, or substring filter",
                    }
                },
            },
            handler=self._tool_types,
        )

        # 3. inventory
        self._register_tool(
            name="samsung_health_inventory",
            description="View local SQLite cache inventory, record counts, and temporal coverage per manifest.",
            input_schema={
                "type": "object",
                "properties": {
                    "manifest_id": {
                        "type": "string",
                        "description": "Optional manifest ID or alias to inspect",
                    }
                },
            },
            handler=self._tool_inventory,
        )

        # 4. analyze
        self._register_tool(
            name="samsung_health_analyze",
            description="Run structured analytics for sleep, daily activity, exercise, or generic types with formula provenance.",
            input_schema={
                "type": "object",
                "required": ["health_type"],
                "properties": {
                    "health_type": {
                        "type": "string",
                        "description": "Metric to analyze (e.g. sleep, activity, exercise, weight)",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["day", "week", "month"],
                        "description": "Temporal aggregation period",
                    },
                    "latest": {
                        "type": "boolean",
                        "description": "Analyze the single latest relevant source record",
                    },
                    "since": {
                        "type": "string",
                        "description": "Start ISO-8601 timestamp or date",
                    },
                    "until": {
                        "type": "string",
                        "description": "End ISO-8601 timestamp or date",
                    },
                    "all_history": {
                        "type": "boolean",
                        "description": "Analyze entire historical local dataset",
                    },
                    "compare": {
                        "type": "string",
                        "enum": ["previous"],
                        "description": "Compare against preceding equivalent period",
                    },
                },
            },
            handler=self._tool_analyze,
        )

        # 5. summary
        self._register_tool(
            name="samsung_health_summary",
            description="Generate a unified multi-metric daily summary across steps, sleep, heart rate, and weight.",
            input_schema={
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "Target date in YYYY-MM-DD format (defaults to current date)",
                    }
                },
            },
            handler=self._tool_summary,
        )

        # 6. cache_status
        self._register_tool(
            name="samsung_health_cache_status",
            description="Inspect SQLite cache table record counts and synchronization error metadata.",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_cache_status,
        )

        # 7. read_records (sensitive / bounded)
        if self.allow_records:
            self._register_tool(
                name="samsung_health_read_records",
                description="Retrieve raw records from local cache with mandatory hard bounding and privacy redaction.",
                input_schema={
                    "type": "object",
                    "required": ["manifest_id"],
                    "properties": {
                        "manifest_id": {
                            "type": "string",
                            "description": "Target manifest ID or human alias",
                        },
                        "since": {
                            "type": "string",
                            "description": "Start ISO-8601 timestamp filter",
                        },
                        "until": {
                            "type": "string",
                            "description": "End ISO-8601 timestamp filter",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": MAX_RECORD_LIMIT,
                            "description": f"Maximum records to retrieve (clamped to {MAX_RECORD_LIMIT})",
                        },
                        "offset": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Pagination offset",
                        },
                    },
                },
                handler=self._tool_read_records,
            )

        # 8. sync (gated)
        if self.allow_sync:
            self._register_tool(
                name="samsung_health_sync",
                description="Synchronize health records from Samsung Cloud into the local mirror database.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "manifest_id": {
                            "type": "string",
                            "description": "Specific manifest to synchronize (or omitted for core types)",
                        },
                        "days": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Days of recent history to sync (default: 14)",
                        },
                        "all_history": {
                            "type": "boolean",
                            "description": "Sync complete historical dataset",
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force sync ignoring cache freshness",
                        },
                    },
                },
                handler=self._tool_sync,
            )

    # Tool implementations
    def _tool_status(self, **_kwargs: Any) -> Any:
        with SamsungHealthClient(config=self.config) as client:
            return client.status()

    def _tool_types(self, query: str | None = None, **_kwargs: Any) -> Any:
        with SamsungHealthLocalClient(config=self.config) as client:
            return client.types(query=query)

    def _tool_inventory(self, manifest_id: str | None = None, **_kwargs: Any) -> Any:
        with SamsungHealthLocalClient(config=self.config) as client:
            return client.inventory(manifest_id=manifest_id)

    def _tool_analyze(
        self,
        health_type: str,
        period: str | None = None,
        latest: bool = False,
        since: str | None = None,
        until: str | None = None,
        all_history: bool = False,
        compare: str | None = None,
        **_kwargs: Any,
    ) -> Any:
        with SamsungHealthLocalClient(config=self.config) as client:
            return client.analyze(
                health_type=health_type,
                period=period,
                latest=latest,
                since=since,
                until=until,
                all_history=all_history,
                compare=compare,
            )

    def _tool_summary(self, day: str | None = None, **_kwargs: Any) -> Any:
        with SamsungHealthLocalClient(config=self.config) as client:
            return client.summary(day=day)

    def _tool_cache_status(self, **_kwargs: Any) -> Any:
        with SamsungHealthLocalClient(config=self.config) as client:
            return client.cache_status()

    def _tool_read_records(
        self,
        manifest_id: str,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
        offset: int = 0,
        **_kwargs: Any,
    ) -> Any:
        # Enforce server-side hard maximum limit
        clamped_limit = min(max(1, int(limit)), MAX_RECORD_LIMIT)
        clamped_offset = max(0, int(offset))
        with SamsungHealthLocalClient(config=self.config) as client:
            records = client.read_data(
                manifest_id=manifest_id,
                since=since,
                until=until,
                limit=clamped_limit,
                offset=clamped_offset,
                envelope=False,
            )
            # Mask sensitive strings and signed URLs
            clean_records = redact_secrets(records)
            return {
                "manifest_id": manifest_id,
                "count": len(clean_records),
                "offset": clamped_offset,
                "limit": clamped_limit,
                "next_offset": clamped_offset + len(clean_records)
                if len(clean_records) == clamped_limit
                else None,
                "records": clean_records,
            }

    def _tool_sync(
        self,
        manifest_id: str | None = None,
        days: int = 14,
        all_history: bool = False,
        force: bool = False,
        **_kwargs: Any,
    ) -> Any:
        with SamsungHealthClient(config=self.config) as client:
            return client.sync(
                manifest_id=manifest_id,
                days=days,
                all_history=all_history,
                force=force,
            )


def create_mcp_server(
    config: HealthConfig | None = None,
    *,
    allow_records: bool = True,
    allow_sync: bool = True,
) -> SamsungHealthMcpServer:
    return SamsungHealthMcpServer(
        config=config,
        allow_records=allow_records,
        allow_sync=allow_sync,
    )


def list_registered_tools(server: SamsungHealthMcpServer) -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in server._tools.values()
    ]


def invoke_tool(
    server: SamsungHealthMcpServer, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if name not in server._tools:
        return error_envelope("tool_not_found", f"unknown MCP tool: {name}")

    tool_def = server._tools[name]
    handler = tool_def["handler"]
    try:
        data = handler(**arguments)
        return envelope(data)
    except UsageError as exc:
        return error_envelope("usage_error", str(exc))
    except SamsungHealthError as exc:
        return error_envelope("health_error", str(exc))
    except Exception as exc:  # noqa: BLE001
        return error_envelope("internal_error", f"{type(exc).__name__}: execution failed")


def run_stdio_server(server: SamsungHealthMcpServer | None = None) -> int:
    """Run JSON-RPC MCP server over stdin/stdout."""
    mcp_server = server or create_mcp_server()

    # Try importing official mcp package if available
    try:
        from mcp.server.fastmcp import FastMCP

        fast_mcp = FastMCP("samsung-health")
        for tool in list_registered_tools(mcp_server):
            name = tool["name"]
            desc = tool["description"]

            def make_handler(tname: str):
                def tool_fn(**kwargs: Any):
                    res = invoke_tool(mcp_server, tname, kwargs)
                    if not res["ok"]:
                        raise RuntimeError(res["error"]["message"])
                    return res["data"]

                return tool_fn

            fast_mcp.add_tool(
                make_handler(name),
                name=name,
                description=desc,
            )

        fast_mcp.run()
        return 0
    except ImportError:
        pass

    # Simple stdio JSON-RPC loop fallback
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": list_registered_tools(mcp_server)},
                }
            elif method == "tools/call":
                tname = params.get("name", "")
                targs = params.get("arguments", {})
                tool_res = invoke_tool(mcp_server, tname, targs)
                if tool_res["ok"]:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(tool_res["data"], indent=2, sort_keys=True),
                                }
                            ]
                        },
                    }
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32000,
                            "message": tool_res["error"]["message"],
                        },
                    }
            elif method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "samsung-health", "version": "0.7.0"},
                    },
                }
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="samsung-health-mcp",
        description="Samsung Health Cloud MCP Server (stdio)",
    )
    parser.add_argument(
        "--timezone", default="UTC", help="Timezone for dates and bounds (default: UTC)"
    )
    parser.add_argument(
        "--master-state",
        type=Path,
        default=None,
        help="Override path to master credentials",
    )
    parser.add_argument("--state", type=Path, default=None, help="Override path to session state")
    parser.add_argument(
        "--catalog", type=Path, default=None, help="Override path to manifests catalog"
    )
    parser.add_argument(
        "--cache",
        "--cache-db",
        dest="cache",
        type=Path,
        default=None,
        help="Override path to SQLite cache",
    )
    parser.add_argument(
        "--no-records", action="store_true", help="Disable raw record retrieval tool"
    )
    parser.add_argument("--no-sync", action="store_true", help="Disable cloud synchronization tool")

    args = parser.parse_args(argv)

    config = HealthConfig(
        master_state_path=args.master_state,
        state_path=args.state,
        cache_path=args.cache,
        catalog_path=args.catalog,
        timezone=args.timezone,
    )

    server = create_mcp_server(
        config=config,
        allow_records=not args.no_records,
        allow_sync=not args.no_sync,
    )

    return run_stdio_server(server)


if __name__ == "__main__":
    raise SystemExit(main())
