"""Terminal strip plan: one table per strip (internal side | wire | terminal | wire | external side).

Internal/external targets come from the strip definition; when empty they are derived from the
netlist built while drawing the schematics: the conductor going to a field/door-mounted device is
the external side, the other one the cabinet side.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.designation import natural_key, split_terminal_ref
from ..domain.model import Mount, Project, SheetSpec, TerminalStrip
from ..drawing import SheetGeometry, add_line, add_rect, add_text
from .context import BuildContext, Wire

ROW_H = 6.0
HEADER_H = 8.0
COLUMNS = [  # (header, width fraction)
    ("Destino interno / Cabinet side", 0.26),
    ("Hilo / Wire", 0.10),
    ("Borne / Term.", 0.08),
    ("Hilo / Wire", 0.10),
    ("Destino externo / Field side", 0.26),
    ("Potencial", 0.10),
    ("Color", 0.10),
]


@dataclass
class TerminalRow:
    strip: str
    number: str
    internal: str
    internal_wire: str
    external: str
    external_wire: str
    potential: str
    color: str


def _is_field(project: Project, ref: str) -> bool:
    tag, _ = split_terminal_ref(ref)
    return project.has_device(tag) and project.device(tag).mount in (Mount.FIELD, Mount.DOOR)


def terminal_rows(project: Project, strip: TerminalStrip, wires: list[Wire]) -> list[TerminalRow]:
    """One row per terminal; the side towards a field/door device is the external side."""
    rows: list[TerminalRow] = []
    for term in sorted(strip.terminals, key=lambda t: natural_key(t.number)):
        ref = f"{strip.tag}:{term.number}"
        connected = [(w, w.from_ref) for w in wires if w.to_ref == ref]
        connected += [(w, w.to_ref) for w in wires if w.from_ref == ref]
        internal = next(((w, other) for w, other in connected if not _is_field(project, other)), None)
        external = next(((w, other) for w, other in connected if _is_field(project, other)), None)
        any_wire = (internal or external or (None, ""))[0]
        potential = term.potential or (any_wire.potential if any_wire and any_wire.potential else "")
        if not potential and term.pe:
            potential = "PE"
        rows.append(
            TerminalRow(
                strip=strip.tag,
                number=term.number,
                internal=term.internal or (internal[1] if internal else ""),
                internal_wire=term.wire or (internal[0].number if internal else ""),
                external=term.external or (external[1] if external else ""),
                external_wire=external[0].number if external else "",
                potential=potential,
                color=any_wire.color_code if any_wire else ("GNYE" if term.pe else ""),
            )
        )
    return rows


def generate_terminal_plan(ctx: BuildContext, spec: SheetSpec) -> list[int]:
    """Tables flow down the page; a new page starts when the next chunk does not fit."""
    created: list[int] = []
    geo: SheetGeometry | None = None
    y = 0.0
    min_block = HEADER_H + 2 * ROW_H + 12.0
    for strip in ctx.project.terminal_strips:
        rows = terminal_rows(ctx.project, strip, ctx.wires)
        index = 0
        while True:
            if geo is None or y - min_block < geo.area[1]:
                geo = ctx.new_page(spec.title, spec.kind.value)
                created.append(geo.number)
                y = geo.area[3] - 4.0
            capacity = max(int((y - geo.area[1] - HEADER_H - 12.0) // ROW_H), 1)
            chunk = rows[index : index + capacity]
            y = _table(ctx, geo, y, strip, chunk)
            index += len(chunk)
            if index >= len(rows):
                break
    return created


def _table(
    ctx: BuildContext, geo: SheetGeometry, top: float, strip: TerminalStrip, rows: list[TerminalRow]
) -> float:
    text = ctx.profile.text
    msp = ctx.msp
    x0, _, x1, _ = geo.area
    x0 += 4.0
    x1 -= 4.0
    width = x1 - x0
    title = f"{ctx.designation(ctx.device(strip.tag)) if ctx.project.has_device(strip.tag) else strip.tag}"
    if strip.description:
        title += f"  –  {strip.description}"
    add_text(msp, title, (x0, top), height=text.designation, layer="E-DESIG", align="TOP_LEFT")
    y = top - text.designation - 2.0
    xs = [x0]
    for _, frac in COLUMNS:
        xs.append(xs[-1] + frac * width)
    xs[-1] = x1
    add_rect(msp, x0, y - HEADER_H, x1, y, layer="E-TITLE")
    for (header, _), cx0, cx1 in zip(COLUMNS, xs, xs[1:], strict=False):
        add_text(
            msp,
            header,
            ((cx0 + cx1) / 2, y - HEADER_H / 2),
            height=text.minimum * 0.9,
            layer="E-TEXT",
            align="MIDDLE_CENTER",
        )
    y -= HEADER_H
    for row in rows:
        values = [
            row.internal,
            row.internal_wire,
            row.number,
            row.external_wire,
            row.external,
            row.potential,
            row.color,
        ]
        add_rect(msp, x0, y - ROW_H, x1, y, layer="E-GRID")
        for value, cx0, cx1 in zip(values, xs, xs[1:], strict=False):
            add_text(
                msp,
                value,
                ((cx0 + cx1) / 2, y - ROW_H / 2),
                height=text.general,
                layer="E-TEXT",
                align="MIDDLE_CENTER",
            )
        y -= ROW_H
    for x in xs:
        add_line(msp, (x, top - text.designation - 2.0), (x, y), layer="E-GRID")
    return y - 10.0
