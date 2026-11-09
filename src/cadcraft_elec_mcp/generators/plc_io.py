"""PLC I/O sheets: one current path per channel.

* Inputs (DI/AI):  supply rail (L+) -> [strip terminal] -> field device -> PLC input terminal (box at the end)
* Outputs (DO/AQ): PLC output terminal (box at the start) -> [strip terminal] -> load -> return rail (M)
"""

from __future__ import annotations

import textwrap

from ..domain.designation import natural_key, split_terminal_ref
from ..domain.model import IoKind, PathElement, PlcIoChannel, PotentialKind, SheetKind, SheetSpec
from ..drawing import add_line, add_rect, add_text
from ..errors import GenerationError
from .context import BuildContext
from .ladder import LadderPath, LadderSheet, paginate

BOX = 30.0  # depth of the module box along the current path (terminal, address, 2-line comment, title)
INPUTS = (IoKind.DI, IoKind.AI)
OUTPUTS = (IoKind.DO, IoKind.AQ)


def _rail(ctx: BuildContext, kind: PotentialKind, default: str) -> str:
    for potential in ctx.project.potentials:
        if potential.kind is kind:
            return potential.name
    return default


def _elements(channel: PlcIoChannel) -> list[PathElement]:
    """Series elements of one channel path.

    Inputs:  L+ -> field device -> strip terminal -> PLC input  (the signal enters the cabinet)
    Outputs: PLC output -> strip terminal -> field device -> M  (the signal leaves the cabinet)
    """
    device: list[PathElement] = []
    if channel.device:
        device.append(
            PathElement(device=channel.device, symbol=channel.symbol, label=channel.description or None)
        )
    terminal: list[PathElement] = []
    if channel.strip_terminal:
        strip, number = split_terminal_ref(channel.strip_terminal)
        if number is None:
            raise GenerationError(f"strip_terminal {channel.strip_terminal!r} needs a number (e.g. -XD2:5)")
        terminal.append(PathElement(device=strip, symbol="terminal", terminals=[[number, number]], label=""))
    return device + terminal if channel.kind in INPUTS else terminal + device


def generate_plc_io(ctx: BuildContext, spec: SheetSpec) -> list[int]:
    if not spec.plc:
        raise GenerationError(f"Sheet {spec.id!r} (plc_io) needs 'plc' (the CPU/module tag).")
    plc = ctx.device(spec.plc)
    kinds = set(spec.io_kinds) or set(IoKind)
    channels = sorted(
        (c for c in ctx.project.plc_io if c.plc == plc.tag and c.kind in kinds),
        key=lambda c: natural_key(c.address),
    )
    if not channels:
        raise GenerationError(
            f"No I/O channels for {plc.tag} ({', '.join(sorted(k.value for k in kinds))}).",
            hint="Assign channels with plc_io_assign first.",
        )
    plus = _rail(ctx, PotentialKind.DC_PLUS, "24V")
    minus = _rail(ctx, PotentialKind.DC_MINUS, "0V")
    created: list[int] = []
    for group, is_input in ((INPUTS, True), (OUTPUTS, False)):
        chans = [c for c in channels if c.kind in group]
        if not chans:
            continue
        paths = [
            LadderPath(
                label=c.address,
                supply=[plus] if is_input else [],
                elements=_elements(c),
                return_rail=None if is_input else minus,
                end_ref=f"{plc.tag}:{c.terminal}" if is_input else None,
                start_ref=None if is_input else f"{plc.tag}:{c.terminal}",
                circuit_kind=PotentialKind.DC_PLUS,
            )
            for c in chans
        ]
        capacity = (
            ctx.profile.sheet.columns if ctx.vertical else ctx.profile.sheet.columns * ctx.profile.sheet.rungs
        )
        pages = paginate(paths, capacity)
        word = "Entradas / Inputs" if is_input else "Salidas / Outputs"
        for i, page in enumerate(pages, start=1):
            title = f"{spec.title} – {word}" + (f" ({i}/{len(pages)})" if len(pages) > 1 else "")
            geo = ctx.new_page(title, spec.kind.value)
            sheet = LadderSheet(
                ctx,
                geo,
                SheetKind.PLC_IO,
                supply_rails=[plus] if is_input else [],
                return_rails=[] if is_input else [minus],
                reserve_start=0.0 if is_input else BOX,
                reserve_end=BOX if is_input else 0.0,
            )
            sheet.draw_rails()
            page_channels = [chans[paths.index(path)] for _, path in page]
            for slot, path in page:
                sheet.draw_path(slot, path)
            _draw_module_box(
                ctx,
                sheet,
                [s for s, _ in page],
                page_channels,
                plc.tag,
                plc.description,
                plc.part_number,
                is_input,
            )
            created.append(geo.number)
    return created


def _draw_module_box(
    ctx: BuildContext,
    sheet: LadderSheet,
    slots: list[int],
    channels: list[PlcIoChannel],
    tag: str,
    description: str,
    part_number: str,
    is_input: bool,
) -> None:
    """Module outline (one per band) with terminal names, addresses and comments per channel."""
    text = ctx.profile.text
    msp = ctx.msp
    title = f"{tag}  {description}".strip() + (f"  ({part_number})" if part_number else "")
    by_band: dict[int, list[tuple[float, PlcIoChannel]]] = {}
    for slot, channel in zip(slots, channels, strict=True):
        band, pos = sheet.slot_position(slot)
        by_band.setdefault(band.index, []).append((pos, channel))

    for band in sheet.bands:
        if band.index not in by_band:
            continue
        if is_input:
            a0, a1 = sheet.box_end_zone(band)
        else:
            a0 = sheet.box_start(band)
            a1 = a0 + BOX
        p0 = sheet.pt(band.across_min + 1.0, a0)
        p1 = sheet.pt(band.across_max - 1.0, a1)
        add_rect(
            msp, min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]), layer="E-SYMBOL"
        )
        if sheet.vertical:
            add_text(
                msp,
                title,
                # on the edge opposite to the channel ports
                sheet.pt(band.across_min + 2.0, a1 - 1.5 if is_input else a0 + 1.5 + text.designation),
                height=text.designation,
                layer="E-DESIG",
                align="BOTTOM_LEFT",
            )
        else:  # narrow vertical box: title runs up along its far edge
            far = a1 - 1.5 if is_input else a0 + 1.5 + text.designation
            add_text(
                msp,
                title,
                (far, band.across_min + 2.0),
                height=text.designation,
                layer="E-DESIG",
                align="BOTTOM_LEFT",
                rotation=90,
            )

        port_edge = a0 if is_input else a1
        inner = 1.0 if is_input else -1.0
        align_inside = "MIDDLE_CENTER" if sheet.vertical else "MIDDLE_LEFT"
        for pos, channel in by_band[band.index]:
            add_line(msp, sheet.pt(pos, port_edge), sheet.pt(pos, port_edge + inner * 1.5), layer="E-SYMBOL")
            x, y = sheet.pt(pos, port_edge + inner * 0.8)
            if sheet.vertical:
                add_text(
                    msp,
                    channel.terminal,
                    (x - 0.8, y),
                    height=text.terminal,
                    layer="E-TERMINAL",
                    align="TOP_RIGHT" if is_input else "BOTTOM_RIGHT",
                )
            else:
                add_text(
                    msp,
                    channel.terminal,
                    (x, y + 0.8),
                    height=text.terminal,
                    layer="E-TERMINAL",
                    align="BOTTOM_LEFT",
                )
            ax, ay = sheet.pt(pos, port_edge + inner * 6.0)
            add_text(msp, channel.address, (ax, ay), height=text.general, layer="E-TEXT", align=align_inside)
            if channel.description:
                width = max(int(sheet.geo.column_width / (text.general * 0.8)), 8) if sheet.vertical else 28
                for j, line in enumerate(textwrap.wrap(channel.description, width)[:2]):
                    lx, ly = sheet.pt(pos, port_edge + inner * (10.0 + j * text.general * 1.3))
                    add_text(msp, line, (lx, ly), height=text.general, layer="E-TEXT", align=align_inside)
