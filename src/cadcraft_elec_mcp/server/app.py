"""MCP server assembly."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .. import __version__
from ..application import Session
from ..config import Settings
from .tools import GROUPS

INSTRUCTIONS = """\
Industrial electrical drawings (IEC 81346/60617/61082/60204-1 or NFPA 79) generated as DXF and published
through CADCraft (PDF, PNG, DWG).

Workflow:
1. project_create (or project_open). Pick profile iec | iec_legacy | nfpa.
2. library_search -> device_add (catalog_id or kind; tags auto-assigned per profile).
   Vendor 2D models: library_import_model (DXF/DWG front view -> clean 1:1 block).
3. potential_set for extra rails; sheet_add power/control sheets with current paths.
4. plc_io_assign + sheet_add(kind=plc_io, plc=...); terminals_assign_io for field wiring.
5. network_link + sheet_add(kind=network).
6. cabinet_configure (+ cabinet_rails / cabinet_place) -> cabinet_plan.
7. validate -> build(previews=[...]) -> sheet_preview(n) to visually check -> fix -> rebuild.
8. cadcraft_open to show the result in the CADCraft desktop app.
All changes are saved immediately in <project>.elec.yaml (source of truth). Reply to the user in Spanish.
"""


def create_server(settings: Settings | None = None) -> MCPServer:
    settings = settings or Settings()
    session = Session(settings)
    server = MCPServer(
        name="cadcraft-elec",
        title="CADCraft Electrical",
        version=__version__,
        instructions=INSTRUCTIONS,
    )
    for group in GROUPS:
        group.register(server, session)
    return server
