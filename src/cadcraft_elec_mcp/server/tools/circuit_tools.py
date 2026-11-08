"""MCP tools: sheets & current paths, PLC I/O, terminal strips, network."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ...application import io_terminals, network, sheets
from ...application.session import Session
from ...domain.model import CircuitPath, IoKind, NetworkLink, SheetKind
from ..annotations import DESTRUCTIVE, READ, WRITE
from ..errors import tool_errors


def register(server: MCPServer, session: Session) -> None:
    # -- sheets -------------------------------------------------------------------------------------
    @server.tool(annotations=WRITE)
    @tool_errors
    def sheet_add(
        kind: SheetKind,
        title: str,
        paths: list[CircuitPath] | None = None,
        plc: str | None = None,
        io_kinds: list[IoKind] | None = None,
        sheet_id: str | None = None,
        note: str = "",
        position: int | None = None,
    ) -> dict[str, Any]:
        """Add a sheet definition. Kinds:

        * power / control: list of current `paths`. Each path: `supply` rails (one per pole, e.g.
          ['L1','L2','L3'] or ['24V']), series `elements` [{device, symbol?, terminals?, label?}],
          optional `return_rail` ('0V', 'N') and `pe`. Symbols/terminals default from the device kind
          (coil A1-A2, contacts 13-14/21-22..., poles 1-2/3-4/5-6). Use symbol 'contact_no'/'contact_nc'
          to draw a relay/contactor contact; cross references are automatic. Long sheets paginate.
        * plc_io: `plc` tag (+ optional io_kinds); draws every channel assigned with plc_io_assign.
        * network: topology of all network links. * cover / terminal_plan / cabinet_layout: automatic.
        """
        return sheets.add_sheet(
            session,
            kind,
            title,
            sheet_id=sheet_id,
            paths=paths,
            plc=plc,
            io_kinds=io_kinds,
            note=note,
            position=position,
        )

    @server.tool(annotations=WRITE)
    @tool_errors
    def sheet_add_paths(sheet_id: str, paths: list[CircuitPath]) -> dict[str, Any]:
        """Append current paths to an existing power/control sheet."""
        return sheets.add_paths(session, sheet_id, paths)

    @server.tool(annotations=WRITE)
    @tool_errors
    def sheet_update(
        sheet_id: str,
        title: str | None = None,
        paths: list[CircuitPath] | None = None,
        plc: str | None = None,
        io_kinds: list[IoKind] | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Replace fields of a sheet (giving `paths` replaces all its paths)."""
        return sheets.update_sheet(
            session,
            sheet_id,
            {"title": title, "paths": paths, "plc": plc, "io_kinds": io_kinds, "note": note},
        )

    @server.tool(annotations=DESTRUCTIVE)
    @tool_errors
    def sheet_remove(sheet_id: str) -> dict[str, str]:
        """Delete a sheet definition."""
        return sheets.remove_sheet(session, sheet_id)

    @server.tool(annotations=WRITE)
    @tool_errors
    def sheet_move(sheet_id: str, position: int) -> list[str]:
        """Move a sheet to a 1-based position in the set (cover stays first, terminal/cabinet sheets last)."""
        return sheets.move_sheet(session, sheet_id, position)

    @server.tool(annotations=READ)
    @tool_errors
    def sheet_get(sheet_id: str) -> dict[str, Any]:
        """Full definition of one sheet."""
        return sheets.get_sheet(session, sheet_id)

    # -- PLC I/O --------------------------------------------------------------------------------------
    @server.tool(annotations=WRITE)
    @tool_errors
    def plc_io_assign(plc: str, channels: list[io_terminals.ChannelInput]) -> list[dict[str, Any]]:
        """Assign PLC channels to field devices. Address (%I0.0, %Q0.0, %IW64) and module terminal
        (DIa.0, DQa.0 ... from the catalog) are auto-assigned when omitted; channel count is checked
        against the catalog."""
        return io_terminals.assign_io(session, plc, channels)

    @server.tool(annotations=DESTRUCTIVE)
    @tool_errors
    def plc_io_remove(plc: str, address: str) -> dict[str, str]:
        """Remove one I/O channel assignment."""
        return io_terminals.remove_io(session, plc, address)

    @server.tool(annotations=READ)
    @tool_errors
    def plc_io_list(plc: str | None = None) -> list[dict[str, Any]]:
        """List I/O assignments (optionally of one PLC)."""
        return io_terminals.list_io(session, plc)

    # -- terminals ----------------------------------------------------------------------------------
    @server.tool(annotations=WRITE)
    @tool_errors
    def terminals_add(
        strip: str | None = None,
        description: str = "",
        count: int = 0,
        numbers: list[str] | None = None,
        potential: str | None = None,
        pe: bool = False,
    ) -> dict[str, Any]:
        """Add terminals to a strip (created when missing; tag auto -XD1.. if omitted). Either `count`
        consecutive numbers or explicit `numbers`. Mark protective-earth terminals with pe=true."""
        return io_terminals.add_terminals(session, strip, description, count, numbers, potential, pe)

    @server.tool(annotations=WRITE)
    @tool_errors
    def terminals_assign_io(
        strip: str | None = None, plc: str | None = None, description: str = "Señales de campo"
    ) -> dict[str, Any]:
        """Route every field-mounted I/O device through its own terminal on `strip` (drawn on the I/O
        sheets and listed in the terminal plan)."""
        return io_terminals.assign_io_terminals(session, strip, plc, description)

    @server.tool(annotations=READ)
    @tool_errors
    def terminals_list() -> list[dict[str, Any]]:
        """Terminal strips with their terminals."""
        return io_terminals.list_strips(session)

    @server.tool(annotations=DESTRUCTIVE)
    @tool_errors
    def terminals_remove(ref: str) -> dict[str, str]:
        """Remove one terminal, e.g. '-XD2:5'."""
        return io_terminals.remove_terminal(session, ref)

    # -- network ------------------------------------------------------------------------------------
    @server.tool(annotations=WRITE)
    @tool_errors
    def network_link(links: list[NetworkLink]) -> list[dict[str, Any]]:
        """Connect device ports: [{a_device, a_port, b_device, b_port, protocol: profinet|ethernet|iolink,
        cable?, length_m?}]. The network sheet draws them as a tree rooted at the PLC."""
        return network.add_links(session, links)

    @server.tool(annotations=DESTRUCTIVE)
    @tool_errors
    def network_unlink(a_device: str, b_device: str) -> dict[str, str]:
        """Remove the link(s) between two devices."""
        return network.remove_link(session, a_device, b_device)

    @server.tool(annotations=READ)
    @tool_errors
    def network_list() -> list[dict[str, Any]]:
        """List network links."""
        return network.list_links(session)
