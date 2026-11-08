"""Current-path ("ladder") layout engine shared by power, control and PLC I/O sheets.

Geometry is expressed in two abstract coordinates and mapped by the profile orientation:
* ``along`` (A): direction of current flow – downward (IEC, vertical) or rightward (NFPA rungs);
* ``across`` (slot + pole offset): column centre (vertical) or rung position (horizontal).

A sheet has *supply rails* at the start side and *return rails* at the end side; every path
occupies one slot, taps its supply rail(s), draws its elements in series and ends on a return
rail, on an anchor (e.g. a PLC input terminal) or on a terminal element (motor, PSU).
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field

from ezdxf.enums import TextEntityAlignment

from ..domain.model import PathElement, PotentialKind, SheetKind
from ..domain.potentials import potential_kind, rail_sort_key
from ..drawing import SheetGeometry, add_dot, add_line, add_text
from ..errors import GenerationError
from ..symbols import BlockRef, default_symbol
from .context import BuildContext, Wire
from .crossref import MASTER_SYMBOLS, SLAVE_SYMBOLS, XrefItem

RAIL_PITCH = 5.0
ELEMENT_GAP = 10.0  # vertical (IEC): room for rotated wire numbers
ELEMENT_GAP_HORIZONTAL = 16.0  # horizontal (NFPA): wire numbers are written along the rung
POLE_PITCH = 7.5
LABEL_ZONE = 10.0
XREF_ZONE_VERTICAL = 16.0
XREF_ZONE_HORIZONTAL = 34.0


@dataclass
class LadderPath:
    label: str
    supply: list[str]
    elements: list[PathElement]
    return_rail: str | None = None
    pe: bool = False
    slot: int | None = None
    start_ref: str | None = None  # path starts at an anchor instead of a rail
    end_ref: str | None = None  # path ends at an anchor instead of a rail
    circuit_kind: PotentialKind | None = None
    poles: int = field(init=False)

    def __post_init__(self) -> None:
        self.poles = max(1, len(self.supply)) if self.start_ref is None else 1


@dataclass
class Band:
    index: int
    slots: list[float]
    across_min: float
    across_max: float
    along_min: float
    along_max: float


@dataclass
class _Cursor:
    along: float
    ref: str | None  # "tag:terminal" or rail name
    from_rail: str | None


class LadderSheet:
    """Draws one page of current paths."""

    def __init__(
        self,
        ctx: BuildContext,
        geo: SheetGeometry,
        sheet_kind: SheetKind,
        supply_rails: list[str],
        return_rails: list[str],
        *,
        reserve_start: float = 0.0,
        reserve_end: float = 0.0,
    ) -> None:
        self.ctx = ctx
        self.geo = geo
        self.sheet_kind = sheet_kind
        self.vertical = ctx.vertical
        self.supply_rails = sorted(dict.fromkeys(supply_rails), key=rail_sort_key)
        self.return_rails = list(dict.fromkeys(return_rails))
        self.reserve_start = reserve_start
        self.reserve_end = reserve_end
        self.text = ctx.profile.text
        self.bands = self._make_bands()
        self.rotation = 0.0 if self.vertical else 90.0
        self.gap = ELEMENT_GAP if self.vertical else ELEMENT_GAP_HORIZONTAL
        self._slot_of: dict[int, tuple[Band, float]] = {}
        index = 0
        for band in self.bands:
            for pos in band.slots:
                self._slot_of[index] = (band, pos)
                index += 1

    # -- geometry --------------------------------------------------------------------------------------
    def _make_bands(self) -> list[Band]:
        x0, y0, x1, y1 = self.geo.area
        if self.vertical:
            slots = [self.geo.column_center(c) for c in range(1, self.geo.columns + 1)]
            return [Band(0, slots, x0, x1, -y1, -y0)]
        bands: list[Band] = []
        count = self.ctx.profile.sheet.columns
        rungs = self.ctx.profile.sheet.rungs
        width = (x1 - x0) / count
        pitch = (y1 - y0) / rungs
        for b in range(count):
            slots = [y1 - (i + 0.5) * pitch for i in range(rungs)]
            bands.append(Band(b, slots, y0, y1, x0 + b * width, x0 + (b + 1) * width))
        return bands

    def slot_position(self, slot: int) -> tuple[Band, float]:
        """(band, across position) of a slot."""
        if slot not in self._slot_of:
            raise GenerationError(f"Slot {slot + 1} does not exist on this sheet (max {self.capacity}).")
        return self._slot_of[slot]

    @property
    def capacity(self) -> int:
        return len(self._slot_of)

    def pt(self, slot_pos: float, along: float, offset: float = 0.0) -> tuple[float, float]:
        if self.vertical:
            return (slot_pos + offset, -along)
        return (along, slot_pos - offset)

    def _start_margin(self) -> float:
        return LABEL_ZONE if self.vertical else 10.0

    def supply_along(self, band: Band, rail: str) -> float:
        k = self.supply_rails.index(rail)
        return band.along_min + self._start_margin() + k * RAIL_PITCH

    def path_start(self, band: Band) -> float:
        n = len(self.supply_rails)
        return band.along_min + self._start_margin() + max(n - 1, 0) * RAIL_PITCH + 5.0 + self.reserve_start

    def return_along(self, band: Band, rail: str) -> float:
        zone = XREF_ZONE_VERTICAL if self.vertical else XREF_ZONE_HORIZONTAL
        k = self.return_rails.index(rail)
        m = len(self.return_rails)
        return band.along_max - zone - (m - 1 - k) * RAIL_PITCH

    def box_start(self, band: Band) -> float:
        """Along position where a module box drawn in the start reserve begins."""
        return band.along_min + self._start_margin()

    def box_end_zone(self, band: Band) -> tuple[float, float]:
        """(start, end) along positions of the end reserve (where an input module box goes)."""
        start = self.path_limit(band) + 6.0
        return start, start + self.reserve_end - 2.0

    def path_limit(self, band: Band) -> float:
        zone = XREF_ZONE_VERTICAL if self.vertical else XREF_ZONE_HORIZONTAL
        first_return = band.along_max - zone - max(len(self.return_rails) - 1, 0) * RAIL_PITCH
        return first_return - 4.0 - self.reserve_end

    def slots_needed(self, path: LadderPath) -> int:
        return slots_needed(path, self.vertical, self._slot_pitch())

    def _slot_pitch(self) -> float:
        slots = self.bands[0].slots
        return abs(slots[1] - slots[0]) if len(slots) > 1 else 10.0

    def slot_ref(self, slot: int) -> str:
        """Cross-reference text for a slot: /sheet.column (IEC) or the ladder line number (NFPA)."""
        if self.vertical:
            return f"/{self.geo.number}.{slot + 1}"
        return str(self.geo.number * 100 + slot + 1)

    def slot_column(self, slot: int) -> int:
        return slot + 1

    # -- rails -----------------------------------------------------------------------------------------
    def draw_rails(self) -> None:
        h = self.text.general
        for band in self.bands:
            for rail in self.supply_rails:
                self._draw_rail(band, rail, self.supply_along(band, rail), h)
            for rail in self.return_rails:
                self._draw_rail(band, rail, self.return_along(band, rail), h)
            if not self.vertical:
                for i, pos in enumerate(band.slots):
                    line_no = self.geo.number * 100 + band.index * len(band.slots) + i + 1
                    add_text(
                        self.ctx.msp,
                        str(line_no),
                        (band.along_min + 1.0, pos),
                        height=h,
                        layer="E-GRID",
                        align="MIDDLE_LEFT",
                    )

    def _draw_rail(self, band: Band, rail: str, along: float, h: float) -> None:
        kind = potential_kind(self.ctx.project, rail)
        layer = self.ctx.profile.wire_layer(kind)
        lo = band.across_min + (0.0 if self.vertical else 1.0)
        hi = band.across_max
        if self.vertical:
            add_line(self.ctx.msp, (lo, -along), (hi, -along), layer=layer)
            add_text(self.ctx.msp, rail, (lo + 0.5, -along + 0.6), height=h, layer="E-TEXT")
        else:
            add_line(self.ctx.msp, (along, lo), (along, hi), layer=layer)
            add_text(self.ctx.msp, rail, (along, hi + 0.6), height=h, layer="E-TEXT", align="BOTTOM_CENTER")

    # -- paths -----------------------------------------------------------------------------------------
    def draw_path(self, slot: int, path: LadderPath) -> None:
        if slot not in self._slot_of:
            raise GenerationError(f"Slot {slot + 1} does not exist on this sheet (max {self.capacity}).")
        band, pos = self._slot_of[slot]
        poles = path.poles
        span = self.slots_needed(path)
        if not self.vertical and span > 1:  # centre the pole group on the reserved rungs
            last = self._slot_of.get(slot + span - 1)
            if last is not None and last[0] is band:
                pos = (pos + last[1]) / 2
        offsets = [(p - (poles - 1) / 2) * POLE_PITCH for p in range(poles)]
        column = self.slot_column(slot)
        self._draw_label(band, pos - (offsets[-1] if not self.vertical else 0.0), path.label)

        # start: one cursor per pole
        cursors: list[_Cursor] = []
        start = self.path_start(band)
        for p in range(poles):
            if path.start_ref is not None:  # e.g. PLC output: wire leaves the module box edge
                cursors.append(_Cursor(start - 5.0, path.start_ref, None))
            else:
                rail = path.supply[p]
                if rail not in self.supply_rails:
                    raise GenerationError(f"Rail {rail!r} is not on this sheet.")
                along = self.supply_along(band, rail)
                add_dot(self.ctx.msp, self.pt(pos, along, offsets[p]), layer=self._layer_for(rail, path))
                cursors.append(_Cursor(along, rail, rail))

        along = start
        ended = False
        for element in path.elements:
            if ended:
                raise GenerationError(
                    f"Element {element.device} comes after a terminal element (motor/PSU) in path "
                    f"{path.label or slot + 1}."
                )
            ended = self._draw_element(band, pos, slot, column, path, element, offsets, cursors, along)
            symbol = self.ctx.symbols.get(self._symbol_id(element))
            along += symbol.length + self.gap
            if along > self.path_limit(band) + self.gap:
                raise GenerationError(
                    f"Path '{path.label or slot + 1}' is too long for one column; split it into two paths.",
                )

        if ended:
            return
        # end of path
        if path.return_rail is not None:
            if path.return_rail not in self.return_rails:
                raise GenerationError(f"Return rail {path.return_rail!r} is not on this sheet.")
            target = self.return_along(band, path.return_rail)
            cursor = cursors[0]
            self._wire(
                pos, offsets[0], cursor, target, path.return_rail, path, column, to_rail=path.return_rail
            )
            add_dot(
                self.ctx.msp, self.pt(pos, target, offsets[0]), layer=self._layer_for(path.return_rail, path)
            )
        elif path.end_ref is not None:
            target = self.path_limit(band) + 4.0 + 2.0
            self._wire(pos, offsets[0], cursors[0], target, path.end_ref, path, column)

    def _symbol_id(self, element: PathElement) -> str:
        if element.symbol:
            return element.symbol
        device = self.ctx.device(element.device)
        return default_symbol(device.kind, self.sheet_kind)

    def _draw_label(self, band: Band, pos: float, label: str) -> None:
        if not label:
            return
        h = self.text.general
        if self.vertical:
            width_chars = max(int(self.geo.column_width / (h * 0.85)), 6)
            lines = textwrap.wrap(label, width_chars)[:3]
            top = band.along_min + 1.0
            for i, line in enumerate(lines):
                add_text(
                    self.ctx.msp,
                    line,
                    (pos, -(top + i * h * 1.25)),
                    height=h,
                    layer="E-TEXT",
                    align="TOP_CENTER",
                )
        else:  # rung description under the rung (below terminal numbers and actuators)
            add_text(
                self.ctx.msp,
                label,
                (self.path_start(band) + 1.0, pos - 8.0),
                height=h,
                layer="E-TEXT",
                align="TOP_LEFT",
            )

    def _layer_for(self, rail: str | None, path: LadderPath) -> str:
        if rail is not None:
            return self.ctx.profile.wire_layer(potential_kind(self.ctx.project, rail))
        return self.ctx.profile.wire_layer(self._circuit_kind(path))

    def _circuit_kind(self, path: LadderPath) -> PotentialKind:
        if path.circuit_kind is not None:
            return path.circuit_kind
        if path.supply:
            return potential_kind(self.ctx.project, path.supply[0])
        return PotentialKind.DC_PLUS

    def _pole_kind(self, path: LadderPath, pole: int) -> PotentialKind:
        if path.start_ref is None and pole < len(path.supply):
            return potential_kind(self.ctx.project, path.supply[pole])
        return self._circuit_kind(path)

    def _wire(
        self,
        pos: float,
        offset: float,
        cursor: _Cursor,
        target_along: float,
        to_ref: str,
        path: LadderPath,
        column: int,
        *,
        pole: int = 0,
        to_rail: str | None = None,
    ) -> None:
        kind = self._pole_kind(path, pole)
        rail_name = cursor.from_rail or to_rail
        if to_rail is not None and potential_kind(self.ctx.project, to_rail) in {
            PotentialKind.AC_NEUTRAL,
            PotentialKind.PE,
            PotentialKind.DC_MINUS,
        }:
            kind = potential_kind(self.ctx.project, to_rail)
        layer = self.ctx.profile.wire_layer(kind)
        p1 = self.pt(pos, cursor.along, offset)
        p2 = self.pt(pos, target_along, offset)
        add_line(self.ctx.msp, p1, p2, layer=layer)
        number = self.ctx.numberer.number(sheet=self.geo.number, column=column, potential=rail_name)
        if abs(target_along - cursor.along) >= 6.0:
            self._wire_number(p1, p2, number)
        color = self.ctx.profile.wire_color(kind)
        self.ctx.add_wire(
            Wire(
                number=number,
                from_ref=cursor.ref or "?",
                to_ref=to_ref,
                potential_kind=kind,
                color_code=color.code,
                cross_section_mm2=self.ctx.profile.cross_sections_mm2.get(kind, 0.75),
                sheet=self.geo.number,
                ref=f"/{self.geo.number}.{column}" if self.vertical else str(self.geo.number * 100 + column),
                potential=rail_name,
            )
        )

    def _wire_number(self, p1: tuple[float, float], p2: tuple[float, float], number: str) -> None:
        h = self.text.wire_number
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        if self.vertical:
            add_text(
                self.ctx.msp,
                number,
                (mx + 0.8 + h, my),
                height=h,
                layer="E-WIRENO",
                align="BOTTOM_CENTER",
                rotation=90,
            )
        else:
            add_text(self.ctx.msp, number, (mx, my + 0.8), height=h, layer="E-WIRENO", align="BOTTOM_CENTER")

    def _draw_element(
        self,
        band: Band,
        pos: float,
        slot: int,
        column: int,
        path: LadderPath,
        element: PathElement,
        offsets: list[float],
        cursors: list[_Cursor],
        along: float,
    ) -> bool:
        """Draw one element at ``along``; returns True when the element terminates the path."""
        device = self.ctx.device(element.device)
        symbol_id = self._symbol_id(element)
        poles = len(offsets)
        ref = self.ctx.symbols.ensure(symbol_id, poles)
        symbol = ref.symbol

        terminals = element.terminals
        if terminals:
            self.ctx.terminals.reserve(device.tag, terminals)
        else:
            terminals = self.ctx.terminals.allocate(device.tag, device.kind, symbol_id, poles)
        while len(terminals) < poles:
            terminals.append(["", ""])

        designation = self.ctx.designation(device)
        columns_used = slots_needed(path, self.vertical, self._slot_pitch()) if self.vertical else 1
        description = element.label if element.label is not None else device.description
        msp = self.ctx.msp

        if symbol.spans_poles:
            self._insert(
                ref,
                self.pt(pos, along),
                designation,
                description,
                None,
                label_at=self._label_point(
                    pos, along, symbol.length, symbol.width_for(poles, POLE_PITCH) / 2
                ),
                columns=columns_used,
            )
            for p in range(poles):
                self._wire(
                    pos,
                    offsets[p],
                    cursors[p],
                    along,
                    f"{device.tag}:{terminals[p][0]}",
                    path,
                    column,
                    pole=p,
                )
                tx, ty = self.pt(pos, along + 1.2, offsets[p])
                add_text(
                    msp,
                    terminals[p][0],
                    (tx - 0.8, ty) if self.vertical else (tx, ty + 0.8),
                    height=self.text.terminal,
                    layer="E-TERMINAL",
                    align="TOP_RIGHT" if self.vertical else "BOTTOM_LEFT",
                )
        else:
            for p in range(poles):
                self._wire(
                    pos,
                    offsets[p],
                    cursors[p],
                    along,
                    f"{device.tag}:{terminals[p][0]}",
                    path,
                    column,
                    pole=p,
                )
                # labels beside the outermost pole (right in IEC, top in NFPA); actuator on pole 0
                labelled = p == (poles - 1 if self.vertical else 0)
                pole_ref = ref if p == 0 else self.ctx.symbols.ensure(symbol_id, 1, secondary=True)
                self._insert(
                    pole_ref,
                    self.pt(pos, along, offsets[p]),
                    designation if labelled else "",
                    description if labelled else "",
                    terminals[p],
                    label_at=self._label_point(pos, along, symbol.length, symbol.half_width - offsets[p]),
                    columns=columns_used,
                )
                if not symbol.terminal_end:
                    cursors[p] = _Cursor(along + symbol.length, f"{device.tag}:{terminals[p][1]}", None)
            if poles > 1:
                a = along + 4.8
                add_line(
                    msp, self.pt(pos, a, offsets[0] - 1.3), self.pt(pos, a, offsets[-1] - 1.3), layer="E-LINK"
                )

        if symbol_id in MASTER_SYMBOLS or symbol_id in SLAVE_SYMBOLS:
            self._register_xref(
                band, pos, slot, device.tag, symbol_id, terminals, along, symbol.length, offsets
            )

        if path.pe and element is path.elements[-1]:
            half = (
                symbol.width_for(poles, POLE_PITCH) / 2
                if symbol.spans_poles
                else -offsets[0] + symbol.half_width
            )
            self._draw_pe(pos, along, symbol.length, half, device.tag, column)
        return symbol.terminal_end

    def _label_point(self, pos: float, along: float, length: float, half: float) -> tuple[float, float]:
        """Horizontal profiles: designation centred above the symbol body."""
        return self.pt(pos, along + length / 2, -(half + 1.0))

    def _insert(
        self,
        ref: BlockRef,
        at: tuple[float, float],
        tag: str,
        description: str,
        terminals: list[str] | None,
        *,
        label_at: tuple[float, float] | None = None,
        columns: int = 1,
    ) -> None:
        blockref = self.ctx.msp.add_blockref(
            ref.name, at, dxfattribs={"layer": "E-SYMBOL", "rotation": self.rotation}
        )
        # NFPA ladders keep descriptions out of the rung (they go to the device list / rung text)
        lines = self._wrap_description(ref, at, description, columns) if self.vertical else [""]
        values = {"TAG": tag, "DESC": lines[0]}
        if terminals is not None:
            values["T1"] = terminals[0]
            # a feed-through terminal has a single number
            values["T2"] = terminals[1] if len(terminals) > 1 and ref.symbol.id != "terminal" else ""
        blockref.add_auto_attribs(values)
        if self.rotation:
            for attrib in blockref.attribs:
                attrib.dxf.rotation = 0.0
                if attrib.dxf.tag == "TAG" and label_at is not None:
                    attrib.set_placement(label_at, align=TextEntityAlignment.BOTTOM_CENTER)
        # continuation lines of a long description, under the DESC attribute
        h = self.text.general
        x = at[0] + self.ctx.symbols.label_x(ref.symbol, ref.poles)
        y = at[1] - ref.symbol.length / 2 - 0.8
        for i, line in enumerate(lines[1:], start=1):
            add_text(self.ctx.msp, line, (x, y - i * h * 1.25), height=h, layer="E-TEXT", align="TOP_LEFT")

    def _wrap_description(
        self, ref: BlockRef, at: tuple[float, float], description: str, columns: int
    ) -> list[str]:
        """Split a description so it stays inside the column(s) of its path (max 3 lines)."""
        if not description:
            return [""]
        column = self.geo.column_at(at[0])
        right = self.geo.column_center(column) + self.geo.column_width * (columns - 0.5)
        available = right - (at[0] + self.ctx.symbols.label_x(ref.symbol, ref.poles)) - 1.0
        chars = max(int(available / (self.text.general * 0.5)), 8)
        lines = textwrap.wrap(description, chars, break_long_words=False) or [""]
        if len(lines) > 3:
            lines = [*lines[:2], textwrap.shorten(" ".join(lines[2:]), chars, placeholder="…")]
        return lines

    def _register_xref(
        self,
        band: Band,
        pos: float,
        slot: int,
        device: str,
        symbol_id: str,
        terminals: list[list[str]],
        along: float,
        length: float,
        offsets: list[float],
    ) -> None:
        if symbol_id in MASTER_SYMBOLS:
            if self.vertical:
                anchor = (pos - self.geo.column_width / 2 + 1.0, -(band.along_max - XREF_ZONE_VERTICAL + 2.0))
            else:
                last_return = (
                    self.return_along(band, self.return_rails[-1])
                    if self.return_rails
                    else band.along_max - XREF_ZONE_HORIZONTAL
                )
                anchor = (last_return + 2.0, pos + 1.2)
        elif self.vertical:  # left of the wire, just below the contact (labels stay on the right)
            anchor = (pos + offsets[0] - 1.0, -(along + length + 0.8))
        else:  # centred under the contact, below its terminal numbers
            anchor = (along + length / 2, pos - offsets[-1] - 4.0)
        pairs = ["-".join(t for t in pair if t) for pair in terminals]
        self.ctx.xrefs.add(
            XrefItem(device, symbol_id, [p for p in pairs if p], self.slot_ref(slot), anchor, self.vertical)
        )

    def _draw_pe(self, pos: float, along: float, length: float, half: float, tag: str, column: int) -> None:
        mid = along + length / 2
        side = -1.0 if self.vertical else 1.0  # away from the designation text
        start = self.pt(pos, mid, side * half)
        end = self.pt(pos, mid, side * (half + 4.0))
        layer = self.ctx.profile.wire_layer(PotentialKind.PE)
        add_line(self.ctx.msp, start, end, layer=layer)
        ground = self.ctx.symbols.ensure("pe_ground")
        self.ctx.msp.add_blockref(ground.name, end, dxfattribs={"layer": layer}).add_auto_attribs(
            {"TAG": "", "DESC": "", "T1": "PE"}
        )
        color = self.ctx.profile.wire_color(PotentialKind.PE)
        self.ctx.add_wire(
            Wire(
                "PE",
                f"{tag}:PE",
                "PE",
                PotentialKind.PE,
                color.code,
                self.ctx.profile.cross_sections_mm2.get(PotentialKind.PE, 2.5),
                self.geo.number,
                f"/{self.geo.number}.{column}",
                "PE",
            )
        )


def slots_needed(path: LadderPath, vertical: bool, slot_pitch: float) -> int:
    """Multi-pole paths need room for the extra poles and their labels."""
    if path.poles <= 1:
        return 1
    if vertical:
        return 2
    return max(2, math.ceil(((path.poles - 1) * POLE_PITCH + 8.0) / slot_pitch))


def paginate(
    paths: list[LadderPath], capacity: int, width: Callable[[LadderPath], int] = lambda _p: 1
) -> list[list[tuple[int, LadderPath]]]:
    """Split paths into pages of ``capacity`` slots, honouring explicit slots when possible."""
    pages: list[list[tuple[int, LadderPath]]] = [[]]
    next_slot = 0
    for path in paths:
        span = width(path)
        wanted = path.slot if path.slot is not None else next_slot
        wanted = max(wanted, next_slot)
        if wanted + span > capacity:
            pages.append([])
            wanted = 0
        pages[-1].append((wanted, path))
        next_slot = wanted + span
    return [page for page in pages if page]
