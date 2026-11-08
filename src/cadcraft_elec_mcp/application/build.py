"""Build pipeline: project -> DXF drawing set (+ fabrication DXF) -> CADCraft PDF/PNG/DWG -> reports.

``compile_project`` is pure (no CADCraft) and is reused by validation and reports; ``build`` writes
files and calls CADCraft.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..domain.model import SheetKind, SheetSpec
from ..drawing import TitleBlockBuilder, new_document
from ..errors import CadCraftError
from ..generators.cabinet_layout import (
    CabinetDrawing,
    build_cabinet_block,
    generate_cabinet_sheet,
    sheet_scale,
)
from ..generators.context import BuildContext
from ..generators.cover import generate_cover
from ..generators.network import generate_network
from ..generators.plc_io import generate_plc_io
from ..generators.schematic import generate_schematic
from ..generators.terminal_plan import generate_terminal_plan
from ..layout import CabinetPlan
from ..logging_setup import get_logger
from ..reports import all_tables, to_csv, to_xlsx
from ..symbols import SymbolLibrary
from ..validation import ValidationContext, ValidationReport, validate
from .cabinet import ResolvedBoxes
from .cabinet import plan as plan_cabinet
from .session import Session

log = get_logger("application.build")

Generator = Callable[[BuildContext, SheetSpec], list[int]]
_FIRST_PASS: dict[SheetKind, Generator] = {
    SheetKind.COVER: generate_cover,
    SheetKind.POWER: generate_schematic,
    SheetKind.CONTROL: generate_schematic,
    SheetKind.PLC_IO: generate_plc_io,
    SheetKind.NETWORK: generate_network,
}


@dataclass
class Compiled:
    ctx: BuildContext
    plan: CabinetPlan | None = None
    boxes: ResolvedBoxes | None = None
    cabinet: CabinetDrawing | None = None
    sheet_pages: dict[str, list[int]] = field(default_factory=dict)


def _file_stem(session: Session) -> str:
    return f"{session.project.info.project_code} - Planos Electricos"


def compile_project(session: Session, *, include_cover: bool = True) -> Compiled:
    project = session.project
    profile = session.profile
    doc = new_document(profile, session.settings.font)
    template = session.settings.title_block_template
    ctx = BuildContext(
        project=project,
        profile=profile,
        doc=doc,
        title_block=TitleBlockBuilder(doc, profile, template if template else None),
        symbols=SymbolLibrary(doc, profile),
    )
    compiled = Compiled(ctx)

    sheets = list(project.sheets)
    if include_cover and not any(s.kind is SheetKind.COVER for s in sheets):
        sheets.insert(0, SheetSpec(id="cover", kind=SheetKind.COVER, title="Portada / Cover"))
    if project.terminal_strips and not any(s.kind is SheetKind.TERMINAL_PLAN for s in sheets):
        sheets.append(SheetSpec(id="terminals", kind=SheetKind.TERMINAL_PLAN, title="Plano de borneras"))
    if project.cabinet and not any(s.kind is SheetKind.CABINET_LAYOUT for s in sheets):
        sheets.append(SheetSpec(id="cabinet", kind=SheetKind.CABINET_LAYOUT, title="Layout de gabinete"))

    # pass 1: sheets that create the netlist; cover first
    ordered = sorted(
        (s for s in sheets if s.kind in _FIRST_PASS), key=lambda s: s.kind is not SheetKind.COVER
    )
    for sheet in ordered:
        compiled.sheet_pages[sheet.id] = _FIRST_PASS[sheet.kind](ctx, sheet)
    # pass 2: sheets that consume the netlist / physical layout
    for sheet in sheets:
        if sheet.kind is SheetKind.TERMINAL_PLAN:
            compiled.sheet_pages[sheet.id] = generate_terminal_plan(ctx, sheet)
        elif sheet.kind is SheetKind.CABINET_LAYOUT:
            plan, boxes = plan_cabinet(session)
            compiled.plan, compiled.boxes = plan, boxes
            labels = {d.tag: ctx.designation(d) for d in project.devices}
            assert project.cabinet is not None
            n = sheet_scale(profile, project.cabinet)
            compiled.cabinet = build_cabinet_block(
                doc, project.cabinet, plan, boxes.door, labels, text_scale=n
            )
            compiled.sheet_pages[sheet.id] = generate_cabinet_sheet(ctx, sheet, compiled.cabinet, n)

    ctx.xrefs.annotate(ctx.msp, profile.text.general)
    for finalize in ctx.finalizers:
        finalize()
    ctx.finish_title_blocks(f"{_file_stem(session)}.dxf")
    return compiled


def run_validation(session: Session, compiled: Compiled | None = None) -> ValidationReport:
    compiled = compiled or compile_project(session)
    if compiled.plan is None and session.project.cabinet is not None:
        compiled.plan, compiled.boxes = plan_cabinet(session)
    vctx = ValidationContext(
        project=session.project,
        profile=session.profile,
        wires=compiled.ctx.wires,
        xrefs=compiled.ctx.xrefs,
        plan=compiled.plan,
        sized_from_default=compiled.boxes.sized_from_default if compiled.boxes else [],
    )
    return validate(vctx)


def _fabrication_dxf(session: Session, compiled: Compiled, path: Path) -> Path:
    """1:1 back plate + door in its own DXF (for the workshop / CNC)."""
    assert session.project.cabinet is not None and compiled.plan is not None and compiled.boxes is not None
    doc = new_document(session.profile, session.settings.font)
    labels = {d.tag: compiled.ctx.designation(d) for d in session.project.devices}
    drawing = build_cabinet_block(doc, session.project.cabinet, compiled.plan, compiled.boxes.door, labels)
    doc.modelspace().add_blockref(drawing.block, (0, 0), dxfattribs={"layer": "L-DEVICE"})
    doc.saveas(path)
    return path


def build(
    session: Session,
    *,
    pdf: bool = True,
    dwg: bool = False,
    previews: list[int] | None = None,
    reports: bool = True,
    include_cover: bool = True,
) -> dict[str, Any]:
    compiled = compile_project(session, include_cover=include_cover)
    out = session.output_dir
    stem = _file_stem(session)
    result: dict[str, Any] = {"pages": [], "files": {}, "warnings": list(compiled.ctx.warnings)}
    for page in compiled.ctx.pages:
        result["pages"].append({"number": page.geometry.number, "title": page.title, "kind": page.kind})

    dxf_path = out / f"{stem}.dxf"
    compiled.ctx.doc.saveas(dxf_path)
    result["files"]["dxf"] = str(dxf_path)
    if compiled.cabinet is not None:
        fab = _fabrication_dxf(
            session, compiled, out / f"{session.project.info.project_code} - Platina Electrica.dxf"
        )
        result["files"]["cabinet_dxf"] = str(fab)
        result["cabinet"] = compiled.plan.to_dict() if compiled.plan else None

    profile = session.profile
    windows = [p.geometry.window for p in compiled.ctx.pages]
    try:
        if pdf:
            pdf_path = session.cadcraft.sheets_pdf(
                dxf_path, out / f"{stem}.pdf", windows, profile.sheet.paper, profile.sheet.height
            )
            result["files"]["pdf"] = str(pdf_path)
        if dwg:
            result["files"]["dwg"] = str(session.cadcraft.to_dwg(dxf_path, out / f"{stem}.dwg"))
        preview_files = []
        for number in previews or []:
            if 1 <= number <= len(windows):
                png = out / "preview" / f"hoja-{number:02d}.png"
                session.cadcraft.preview_png(dxf_path, png, windows[number - 1], profile.sheet.paper)
                preview_files.append(str(png))
        if preview_files:
            result["files"]["previews"] = preview_files
    except CadCraftError as exc:
        result["warnings"].append(f"CADCraft step failed: {exc}")
        log.error("CADCraft step failed: %s", exc)

    if reports:
        tables = all_tables(session.project, compiled.ctx.wires)
        result["files"]["xlsx"] = str(
            to_xlsx(
                tables,
                out / f"{session.project.info.project_code} - Listas.xlsx",
                title=session.project.info.project_title,
            )
        )
        result["files"]["csv"] = [
            str(p) for p in to_csv(tables, out / "csv", session.project.info.project_code)
        ]

    report = run_validation(session, compiled)
    result["validation"] = {"ok": report.ok, "errors": report.errors, "warnings": report.warnings}
    result["wires"] = len(compiled.ctx.wires)
    return result


def preview_sheet(session: Session, number: int) -> Path:
    """Render one sheet to PNG (rebuilds the DXF so the preview is never stale)."""
    compiled = compile_project(session)
    pages = compiled.ctx.pages
    if not 1 <= number <= len(pages):
        from ..errors import NotFoundError

        raise NotFoundError(f"Sheet {number} does not exist (1..{len(pages)}).")
    out = session.output_dir
    dxf_path = out / f"{_file_stem(session)}.dxf"
    compiled.ctx.doc.saveas(dxf_path)
    png = out / "preview" / f"hoja-{number:02d}.png"
    return session.cadcraft.preview_png(
        dxf_path, png, pages[number - 1].geometry.window, session.profile.sheet.paper
    )
