"""The MCP layer: tool registration, schemas, error translation (in-process, no stdio)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from cadcraft_elec_mcp.config import Settings
from cadcraft_elec_mcp.server.app import create_server


def _call(server: Any, name: str, args: dict[str, Any]) -> Any:
    return asyncio.run(server.call_tool(name, args))


def test_tools_registered(settings: Settings) -> None:
    server = create_server(settings)
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    for expected in (
        "project_create",
        "device_add",
        "sheet_add",
        "plc_io_assign",
        "network_link",
        "cabinet_configure",
        "validate",
        "build",
        "sheet_preview",
        "cadcraft_status",
    ):
        assert expected in tools
    assert tools["validate"].annotations.read_only_hint is True
    assert "items" in tools["device_add"].input_schema["properties"]


def test_tool_flow_and_errors(settings: Settings) -> None:
    server = create_server(settings)
    result = _call(server, "project_create", {"project_code": "MCP1", "project_title": "Via MCP"})
    assert not result.is_error
    result = _call(server, "device_add", {"items": [{"kind": "relay"}, {"catalog_id": "generic-mcb-1p"}]})
    assert not result.is_error, result
    listing = _call(server, "device_list", {})
    assert "-KF1" in str(listing.content)
    with pytest.raises(ToolError, match="not_found"):
        _call(server, "device_add", {"items": [{"catalog_id": "nope"}]})
    report = _call(server, "validate", {})
    assert not report.is_error
