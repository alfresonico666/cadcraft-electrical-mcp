"""MCP tool groups. Each module exposes ``register(server, session)``."""

from . import circuit_tools, device_tools, output_tools, project_tools

GROUPS = (project_tools, device_tools, circuit_tools, output_tools)

__all__ = ["GROUPS"]
