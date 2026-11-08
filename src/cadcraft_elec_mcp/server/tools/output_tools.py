"""MCP tools: cabinet layout, validation, build, previews, reports, CADCraft bridge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Image, MCPServer

from ...application import build as build_uc
from ...application import cabinet
from ...application.session import Session
from ...errors import NotFoundError
from ...reports import all_tables, to_csv, to_xlsx
from ..annotations import EXTERNAL, READ, WRITE
from ..errors import tool_errors


def register(server: MCPServer, session: Session) -> None:
    # -- cabinet ------------------------------------------------------------------------------------
    @server.tool(annotations=WRITE)
    @tool_errors
    def cabinet_configure(
        enclosure_catalog_id: str | None = None,
        enclosure_width: float | None = None,
        enclosure_height: float | None = None,
        enclosure_depth: float | None = None,
        plate_width: float | None = None,
        plate_height: float | None = None,
        plate_margin: float | None = None,
        duct_width: float | None = None,
        duct_depth: float | None = None,
        vertical_ducts: bool | None = None,
        duct_clearance: float | None = None,
        device_gap: float | None = None,
        door_devices: list[str] | None = None,
        spare_ratio: float | None = None,
    ) -> dict[str, Any]:
        """Configure the enclosure and mounting plate (mm). Defaults: 400x500x250 enclosure, 350x450 plate,
        40x60 wire ducts, 10 mm duct clearance, 20 % spare rail length."""
        return cabinet.configure(
            session,
            {
                "enclosure_catalog_id": enclosure_catalog_id,
                "enclosure_width": enclosure_width,
                "enclosure_height": enclosure_height,
                "enclosure_depth": enclosure_depth,
                "plate_width": plate_width,
                "plate_height": plate_height,
                "plate_margin": plate_margin,
                "duct_width": duct_width,
                "duct_depth": duct_depth,
                "vertical_ducts": vertical_ducts,
                "duct_clearance": duct_clearance,
                "device_gap": device_gap,
                "door_devices": door_devices,
                "spare_ratio": spare_ratio,
            },
        )

    @server.tool(annotations=WRITE)
    @tool_errors
    def cabinet_rails(rails: list[list[str]]) -> dict[str, Any]:
        """Fix which devices go on each DIN rail, top to bottom, left to right (e.g. [["-QB1","-FC1"],
        ["-KF1","-TB1"]]). An empty list returns to automatic filling."""
        return cabinet.set_rails(session, rails)

    @server.tool(annotations=WRITE)
    @tool_errors
    def cabinet_place(tag: str, x: float | None = None, y: float | None = None) -> dict[str, Any]:
        """Place a device manually (lower-left corner, plate coordinates, mm). Omit x/y to return to auto."""
        return cabinet.place(session, tag, x, y)

    @server.tool(annotations=READ)
    @tool_errors
    def cabinet_plan() -> dict[str, Any]:
        """Compute the back-plate layout without drawing: device positions, rails, fill %, warnings."""
        plan, boxes = cabinet.plan(session)
        data = plan.to_dict()
        data["door_devices"] = [b.tag for b in boxes.door]
        data["default_sized"] = boxes.sized_from_default
        return data

    # -- quality & outputs ----------------------------------------------------------------------------
    @server.tool(annotations=READ)
    @tool_errors
    def validate() -> dict[str, Any]:
        """Check the project against the standards profile and consistency rules (designations, I/O,
        ports, terminals, cross references, cabinet fit/spare space ...)."""
        return build_uc.run_validation(session).to_dict()

    @server.tool(annotations=EXTERNAL)
    @tool_errors
    def build(
        pdf: bool = True,
        dwg: bool = False,
        previews: list[int] | None = None,
        reports: bool = True,
        include_cover: bool = True,
    ) -> dict[str, Any]:
        """Generate the drawing set: DXF (all sheets), multi-page PDF (via CADCraft), optional DWG, the 1:1
        fabrication DXF of the back plate, XLSX/CSV lists and PNG previews of the sheet numbers in
        `previews`. Returns file paths, page list and a validation summary."""
        return build_uc.build(
            session, pdf=pdf, dwg=dwg, previews=previews, reports=reports, include_cover=include_cover
        )

    @server.tool(annotations=EXTERNAL, structured_output=False)
    @tool_errors
    def sheet_preview(number: int) -> list[Any]:
        """Render one sheet (1-based page number) to PNG with CADCraft and return the image to inspect."""
        png = build_uc.preview_sheet(session, number)
        return [f"Hoja {number}: {png}", Image(path=png)]

    @server.tool(annotations=WRITE)
    @tool_errors
    def reports(csv: bool = True) -> dict[str, Any]:
        """Export BOM, wire list, terminal list, PLC I/O list and network list to XLSX (+ CSV)."""
        compiled = build_uc.compile_project(session)
        tables = all_tables(session.project, compiled.ctx.wires)
        code = session.project.info.project_code
        out = session.output_dir
        result: dict[str, Any] = {
            "xlsx": str(to_xlsx(tables, out / f"{code} - Listas.xlsx", session.project.info.project_title)),
            "tables": {t.name: len(t.rows) for t in tables},
        }
        if csv:
            result["csv"] = [str(p) for p in to_csv(tables, out / "csv", code)]
        return result

    # -- CADCraft bridge --------------------------------------------------------------------------------
    @server.tool(annotations=READ)
    @tool_errors
    def cadcraft_status() -> dict[str, Any]:
        """CADCraft installation, version and whether the desktop app control port is reachable."""
        return session.cadcraft.status()

    @server.tool(annotations=EXTERNAL)
    @tool_errors
    def cadcraft_open(path: str | None = None, which: str = "drawings") -> dict[str, Any]:
        """Open a file in the CADCraft desktop app (launches `cadcraft --control <port>` if needed).
        Without `path`: which='drawings' (sheet set DXF) or 'cabinet' (1:1 plate DXF) of the last build."""
        if path is None:
            code = session.project.info.project_code
            name = (
                f"{code} - Planos Electricos.dxf"
                if which == "drawings"
                else f"{code} - Platina Electrica.dxf"
            )
            target = session.output_dir / name
        else:
            target = Path(path)
        if not target.is_file():
            raise NotFoundError(f"{target} does not exist.", hint="Run build first.")
        return session.cadcraft.open_in_app(target)

    @server.tool(annotations=EXTERNAL)
    @tool_errors
    def cadcraft_execute(command: str, params: dict[str, Any] | None = None) -> Any:
        """Escape hatch: run any CADCraft engine command in the running app (e.g. 'zoom', 'layer.set').
        Needs the desktop app started with --control. Prefer the domain tools for drawing content."""
        return session.cadcraft.execute(command, params or {})
