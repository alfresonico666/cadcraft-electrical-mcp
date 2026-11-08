"""Cover sheet: project identification + sheet index (filled once all pages exist)."""

from __future__ import annotations

from ..domain.model import SheetSpec
from ..drawing import SheetGeometry, add_line, add_text
from .context import BuildContext


def generate_cover(ctx: BuildContext, spec: SheetSpec) -> list[int]:
    geo = ctx.new_page(spec.title, spec.kind.value)
    info = ctx.project.info
    text = ctx.profile.text
    x0, _, x1, y1 = geo.area
    cx = (x0 + x1) / 2
    msp = ctx.msp
    add_text(
        msp,
        info.project_title or info.project_code,
        (cx, y1 - 25),
        height=text.title * 1.5,
        layer="E-TEXT",
        align="MIDDLE_CENTER",
    )
    add_text(
        msp,
        "Diagramas eléctricos / Electrical drawings",
        (cx, y1 - 38),
        height=text.heading,
        layer="E-TEXT",
        align="MIDDLE_CENTER",
    )
    rows = [
        ("Proyecto / Project", info.project_code),
        ("Máquina / Machine", info.machine),
        ("Cliente / Client", info.client),
        ("Planta / Plant", info.plant),
        ("Empresa / Company", info.company),
        ("Norma / Standard", ctx.profile.title),
        ("Revisión / Revision", f"{info.revision}  ({info.date})"),
    ]
    y = y1 - 55
    for label, value in rows:
        if not value:
            continue
        add_text(msp, label, (x0 + 15, y), height=text.general, layer="E-TEXT")
        add_text(msp, value, (x0 + 65, y), height=text.designation, layer="E-TEXT")
        y -= 7.5
    if info.description:
        add_text(msp, info.description, (x0 + 15, y - 4), height=text.general, layer="E-TEXT")
    ctx.finalizers.append(lambda: _sheet_index(ctx, geo))
    return [geo.number]


def _sheet_index(ctx: BuildContext, geo: SheetGeometry) -> None:
    text = ctx.profile.text
    msp = ctx.msp
    x0, _, x1, y1 = geo.area
    left = (x0 + x1) / 2 + 20
    right = x1 - 10
    y = y1 - 55
    add_text(msp, "Índice / Index", (left, y + 6), height=text.heading, layer="E-TEXT")
    add_line(msp, (left, y + 4), (right, y + 4), layer="E-TITLE")
    step = text.general * 2.0
    for page in ctx.pages:
        add_text(
            msp,
            str(page.geometry.number),
            (left + 2, y),
            height=text.general,
            layer="E-TEXT",
            align="TOP_LEFT",
        )
        add_text(msp, page.title, (left + 14, y), height=text.general, layer="E-TEXT", align="TOP_LEFT")
        y -= step
