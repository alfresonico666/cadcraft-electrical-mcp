"""MCP tools: device catalog and project devices."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ...application import devices
from ...application.session import Session
from ...domain.model import DeviceKind, Mount
from ...errors import LibraryError, NotFoundError
from ...library import CatalogEntry, import_model
from ..annotations import DESTRUCTIVE, READ, WRITE
from ..errors import tool_errors


def register(server: MCPServer, session: Session) -> None:
    @server.tool(annotations=READ)
    @tool_errors
    def library_search(
        query: str = "", kind: DeviceKind | None = None, limit: int = 40
    ) -> list[dict[str, Any]]:
        """Search the device catalog (built-in typical devices + your imported vendor models).

        Example queries: 'S7-1200', 'balluff hub', 'mcb 2p', 'psu 24'.
        """
        return [
            e.model_dump(mode="json", exclude_none=True) for e in session.catalog.search(query, kind, limit)
        ]

    @server.tool(annotations=WRITE)
    @tool_errors
    def library_import_model(
        source_path: str,
        catalog_id: str,
        description: str = "",
        kind: DeviceKind = DeviceKind.GENERIC,
        mount: Mount = Mount.DIN_RAIL,
        manufacturer: str = "",
        part_number: str = "",
        ports: list[str] | None = None,
        scale: float | None = None,
        target_width_mm: float | None = None,
        keep_dimensions: bool = False,
        keep_texts: bool = True,
    ) -> dict[str, Any]:
        """Clean a vendor 2D model (DXF or DWG front view) into a 1:1 mm block and add it to your catalog.

        Removes CADENAS ATTDEFs, connection points and (by default) dimensions, converts DWG through
        CADCraft, moves the lower-left corner to 0,0. Use `target_width_mm` (real device width) when
        the file is not drawn in mm. The cleaned DXF goes to <workspace>/library.
        """
        src = Path(source_path)
        if not src.is_file():
            raise LibraryError(f"File not found: {src}")
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in catalog_id)
        dest = session.settings.models_dir / f"{safe}.dxf"
        report = import_model(
            src,
            dest,
            cadcraft=session.cadcraft,
            scale=scale,
            target_width_mm=target_width_mm,
            keep_dimensions=keep_dimensions,
            keep_texts=keep_texts,
        )
        geometry: dict[str, Any] = {
            "width_mm": report.width_mm,
            "height_mm": report.height_mm,
            "model_dxf": str(report.path),
        }
        try:  # existing entry (e.g. built-in S7-1200): keep its I/O, ports, terminals; add the model
            base = session.catalog.get(catalog_id)
            overrides = {
                "manufacturer": manufacturer,
                "part_number": part_number,
                "description": description,
                "ports": ports,
            }
            entry = base.model_copy(update={**{k: v for k, v in overrides.items() if v}, **geometry})
        except NotFoundError:
            entry = CatalogEntry(
                id=catalog_id,
                manufacturer=manufacturer,
                part_number=part_number,
                description=description,
                kind=kind,
                mount=mount,
                ports=list(ports or []),
                **geometry,
            )
        catalog_file = session.catalog.upsert_user_entry(entry)
        return {
            "model_dxf": str(report.path),
            "width_mm": report.width_mm,
            "height_mm": report.height_mm,
            "scale_applied": report.scale,
            "source_insunits": report.source_units,
            "entities": report.kept,
            "removed": report.removed,
            "catalog_file": str(catalog_file),
        }

    @server.tool(annotations=WRITE)
    @tool_errors
    def device_add(items: list[devices.DeviceInput]) -> list[dict[str, Any]]:
        """Add one or more devices. Give `catalog_id` (see library_search) or at least `kind`.

        Tags are auto-assigned from the profile letter code when omitted (-QA1, -KF2 ... or CR1, M1 in NFPA).
        Use mount='field' for devices outside the cabinet, 'door' for door-mounted ones.
        A terminal_strip device also creates its (empty) strip.
        """
        return devices.add_devices(session, items)

    @server.tool(annotations=WRITE)
    @tool_errors
    def device_update(
        tag: str,
        new_tag: str | None = None,
        description: str | None = None,
        manufacturer: str | None = None,
        part_number: str | None = None,
        function: str | None = None,
        location: str | None = None,
        mount: Mount | None = None,
        ports: list[str] | None = None,
        width_mm: float | None = None,
        height_mm: float | None = None,
        model_dxf: str | None = None,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Change device data. Renaming (`new_tag`) updates all references (sheets, I/O, network, cabinet)."""
        changes = {
            "tag": new_tag,
            "description": description,
            "manufacturer": manufacturer,
            "part_number": part_number,
            "function": function,
            "location": location,
            "mount": mount,
            "ports": ports,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "model_dxf": model_dxf,
            "data": data,
        }
        return devices.update_device(session, tag, changes)

    @server.tool(annotations=DESTRUCTIVE)
    @tool_errors
    def device_remove(tag: str, force: bool = False) -> dict[str, Any]:
        """Remove a device. Fails if it is referenced unless force=true (then references are removed too)."""
        return devices.remove_device(session, tag, force)

    @server.tool(annotations=READ)
    @tool_errors
    def device_list(kind: DeviceKind | None = None) -> list[dict[str, Any]]:
        """List project devices (optionally of one kind)."""
        return devices.list_devices(session, kind)
