from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .client import SamsungHealthClient, SamsungHealthLocalClient
from .config import HealthConfig
from .exceptions import SamsungHealthError, UsageError
from .serialization import envelope, error_envelope, redact_raw_records
from .state import StateStore

__all__ = [
    "SamsungHealthMcpServer",
    "create_mcp_server",
    "invoke_tool",
    "list_registered_tools",
    "main",
    "run_stdio_server",
]

MAX_RECORD_LIMIT = 50
MAX_SYNC_DAYS = 90
_MANIFEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


class SamsungHealthMcpServer:
    """Stdio-based Model Context Protocol (MCP) server for Samsung Health Cloud."""

    def __init__(
        self,
        config: HealthConfig | None = None,
        *,
        allow_records: bool = False,
        allow_sync: bool = False,
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
        *,
        read_only: bool = True,
        destructive: bool = False,
        idempotent: bool = True,
        open_world: bool = False,
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "annotations": {
                "readOnlyHint": read_only,
                "destructiveHint": destructive,
                "idempotentHint": idempotent,
                "openWorldHint": open_world,
            },
            "handler": handler,
        }

    def _register_default_tools(self) -> None:
        # 1. status (strictly offline local inspection)
        self._register_tool(
            name="samsung_health_status",
            description="Inspect local authentication token presence and expiration timestamps without exposing secrets.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
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
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                "additionalProperties": False,
            },
            handler=self._tool_summary,
        )

        # 6. cache_status
        self._register_tool(
            name="samsung_health_cache_status",
            description="Inspect SQLite cache table record counts and synchronization error metadata.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=self._tool_cache_status,
        )

        # 7. read_records (sensitive / bounded / opt-in)
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
                    "additionalProperties": False,
                },
                handler=self._tool_read_records,
            )

        # 8. sync (opt-in)
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
                            "maximum": MAX_SYNC_DAYS,
                            "description": f"Days of recent history to sync (1-{MAX_SYNC_DAYS}, default: 14)",
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force sync ignoring cache freshness",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._tool_sync,
                read_only=False,
                destructive=False,
                idempotent=False,
                open_world=True,
            )

    # Tool implementations
    def _tool_status(self, **_kwargs: Any) -> Any:
        store = StateStore(self.config.state_path)
        state = store.load()
        return {
            "health_access_token_present": bool(state.health_access_token),
            "health_access_expires_at": state.health_access_expires_at,
            "health_refresh_token_present": bool(state.health_refresh_token),
            "health_refresh_expires_at": state.health_refresh_expires_at,
            "cloud_token_present": bool(state.cloud_token),
            "cloud_expires_at": state.cloud_expires_at,
            "registration_present": bool(state.registration_id),
            "user_id_present": bool(state.user_id),
            "cdid_present": bool(state.cdid),
            "master_state_present": self.config.master_state_path.exists(),
        }

    def _tool_types(self, query: str | None = None, **_kwargs: Any) -> Any:
        if query and (len(query) > 100 or not _MANIFEST_ID_PATTERN.fullmatch(query)):
            raise UsageError("invalid manifest query parameter")
        with SamsungHealthLocalClient(config=self.config) as client:
            return client.types(query=query)

    def _tool_inventory(self, manifest_id: str | None = None, **_kwargs: Any) -> Any:
        if manifest_id and (
            len(manifest_id) > 100 or not _MANIFEST_ID_PATTERN.fullmatch(manifest_id)
        ):
            raise UsageError("invalid manifest ID parameter")
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
        if (
            not health_type
            or len(health_type) > 100
            or not _MANIFEST_ID_PATTERN.fullmatch(health_type)
        ):
            raise UsageError("invalid health_type parameter")
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
        if day and len(day) > 30:
            raise UsageError("invalid date parameter length")
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
        if (
            not manifest_id
            or len(manifest_id) > 100
            or not _MANIFEST_ID_PATTERN.fullmatch(manifest_id)
        ):
            raise UsageError("invalid manifest_id parameter")
        clamped_limit = limit
        clamped_offset = offset
        with SamsungHealthLocalClient(config=self.config) as client:
            records = client.read_data(
                manifest_id=manifest_id,
                since=since,
                until=until,
                limit=clamped_limit,
                offset=clamped_offset,
                envelope=False,
            )
            clean_records = redact_raw_records(records)
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
        force: bool = False,
        **_kwargs: Any,
    ) -> Any:
        if manifest_id and (
            len(manifest_id) > 100 or not _MANIFEST_ID_PATTERN.fullmatch(manifest_id)
        ):
            raise UsageError("invalid manifest_id parameter")
        clamped_days = days
        with SamsungHealthClient(config=self.config) as client:
            return client.sync(
                manifest_id=manifest_id,
                days=clamped_days,
                all_history=False,
                force=force,
            )


def create_mcp_server(
    config: HealthConfig | None = None,
    *,
    allow_records: bool = False,
    allow_sync: bool = False,
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
            "annotations": tool["annotations"],
        }
        for tool in server._tools.values()
    ]


def invoke_tool(
    server: SamsungHealthMcpServer, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if name not in server._tools:
        return error_envelope("tool_not_found", f"unknown or disabled MCP tool: {name}")

    tool_def = server._tools[name]
    validation_error = _validate_arguments(tool_def.get("inputSchema", {}), arguments)
    if validation_error:
        return error_envelope("invalid_arguments", validation_error)

    handler = tool_def["handler"]
    try:
        data = handler(**arguments)
        return envelope(data)
    except UsageError as exc:
        return error_envelope("invalid_arguments", str(exc))
    except SamsungHealthError as exc:
        return error_envelope("health_error", str(exc))
    except Exception:  # noqa: BLE001
        return error_envelope("internal_error", "An internal error occurred during tool execution.")


def _validate_arguments(schema: dict[str, Any], arguments: Any) -> str | None:
    """Validate the exact JSON subset used by MCP schemas without Python coercion."""
    if not isinstance(arguments, dict):
        return "arguments must be a JSON object"
    properties = schema.get("properties", {})
    unknown = set(arguments) - set(properties)
    if unknown:
        return f"unknown argument(s): {', '.join(sorted(unknown))}"
    missing = set(schema.get("required", [])) - set(arguments)
    if missing:
        return f"missing required argument(s): {', '.join(sorted(missing))}"
    json_types = {
        "string": lambda value: isinstance(value, str),
        "boolean": lambda value: isinstance(value, bool),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
    }
    for key, value in arguments.items():
        spec = properties[key]
        expected = spec.get("type")
        check = json_types.get(expected)
        if check is not None and not check(value):
            return f"argument {key} must have JSON type {expected}"
        if "enum" in spec and value not in spec["enum"]:
            return f"argument {key} is not an allowed value"
        if "minimum" in spec and value < spec["minimum"]:
            return f"argument {key} is below its minimum"
        if "maximum" in spec and value > spec["maximum"]:
            return f"argument {key} exceeds its maximum"
    return None


def run_stdio_server(server: SamsungHealthMcpServer | None = None) -> int:
    """Run the pinned official MCP SDK server over stdio."""
    mcp_server = server or create_mcp_server()
    try:
        import anyio
        from mcp.server import NotificationOptions
        from mcp.server.lowlevel import Server
        from mcp.server.models import InitializationOptions
        from mcp.server.stdio import stdio_server
        from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
    except ImportError as exc:
        raise SamsungHealthError("MCP support requires installation with the 'mcp' extra") from exc

    official = Server("samsung-re-health", version="0.7.2")

    @official.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
                annotations=ToolAnnotations(**tool["annotations"]),
            )
            for tool in list_registered_tools(mcp_server)
        ]

    @official.call_tool(validate_input=True)
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        result = invoke_tool(mcp_server, name, arguments)
        payload = result.get("data") if result["ok"] else result["error"]
        import json

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, sort_keys=True))],
            structuredContent=payload if isinstance(payload, dict) else None,
            isError=not result["ok"],
        )

    async def serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await official.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="samsung-re-health",
                    server_version="0.7.2",
                    capabilities=official.get_capabilities(NotificationOptions(), {}),
                ),
            )

    anyio.run(serve)

    return 0


def main(argv: list[str] | None = None) -> int:
    import os
    import sys

    prog_name = os.path.basename(sys.argv[0]) if sys.argv else "samsung-re-health-mcp"
    if "samsung-health-mcp" in prog_name and "samsung-re-health-mcp" not in prog_name:
        print(
            "Warning: 'samsung-health-mcp' MCP command is deprecated; please use 'samsung-re-health-mcp'.",
            file=sys.stderr,
        )

    parser = argparse.ArgumentParser(
        prog="samsung-re-health-mcp",
        description="Unofficial reverse-engineered Samsung Health SDK, JSON CLI & MCP server (stdio)",
    )
    parser.add_argument(
        "--timezone",
        default=None,
        help="Timezone for dates and bounds (default: UTC or environment)",
    )
    parser.add_argument(
        "--master-state", type=Path, default=None, help="Override path to master credentials"
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
        "--allow-records", action="store_true", help="Opt-in to enable raw record retrieval tool"
    )
    parser.add_argument(
        "--allow-sync", action="store_true", help="Opt-in to enable cloud synchronization tool"
    )

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
        allow_records=args.allow_records,
        allow_sync=args.allow_sync,
    )

    return run_stdio_server(server)


if __name__ == "__main__":
    raise SystemExit(main())
