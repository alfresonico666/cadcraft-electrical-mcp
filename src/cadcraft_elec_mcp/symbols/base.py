"""Symbol definition primitives.

Convention (all symbols, both styles): the symbol is drawn in a block, *vertical*, with the input
connection at (0, 0) and the output at (0, -length). Actuators go on the -x side, labels on +x.
Horizontal (NFPA ladder) sheets insert the same blocks rotated +90 deg.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from ezdxf.layouts import BlockLayout

LABEL_X = 4.0  # distance of the designation text from the wire axis


class Pen:
    """Small drawing helper bound to one block (geometry on layer 0 -> inherits the INSERT layer)."""

    def __init__(self, block: BlockLayout, *, with_actuator: bool = True) -> None:
        self.block = block
        # secondary poles of a multi-pole device are drawn without the operating means (actuator)
        self.with_actuator = with_actuator

    def line(self, x1: float, y1: float, x2: float, y2: float, *, linetype: str | None = None) -> None:
        attribs = {"layer": "0"}
        if linetype:
            attribs["linetype"] = linetype
        self.block.add_line((x1, y1), (x2, y2), dxfattribs=attribs)

    def poly(self, points: list[tuple[float, float]], *, closed: bool = False) -> None:
        self.block.add_lwpolyline(points, close=closed, dxfattribs={"layer": "0"})

    def rect(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], closed=True)

    def circle(self, cx: float, cy: float, r: float) -> None:
        self.block.add_circle((cx, cy), r, dxfattribs={"layer": "0"})

    def arc(self, cx: float, cy: float, r: float, start: float, end: float) -> None:
        self.block.add_arc((cx, cy), r, start, end, dxfattribs={"layer": "0"})

    def dot(self, cx: float, cy: float, r: float = 0.5) -> None:
        self.block.add_circle((cx, cy), r, dxfattribs={"layer": "0"})
        hatch = self.block.add_hatch(dxfattribs={"layer": "0"})
        hatch.paths.add_edge_path().add_arc((cx, cy), r, 0, 360)

    def text(self, x: float, y: float, value: str, height: float = 2.5, align: str = "MIDDLE_CENTER") -> None:
        from ezdxf.enums import TextEntityAlignment

        txt = self.block.add_text(value, height=height, dxfattribs={"layer": "0", "style": "ELEC"})
        txt.set_placement((x, y), align=TextEntityAlignment[align])

    def stub_in(self, y: float) -> None:
        """Lead from the input connection (0,0) down to ``y``."""
        self.line(0, 0, 0, y)

    def stub_out(self, y: float, length: float) -> None:
        self.line(0, y, 0, -length)

    def diag(self, x1: float, y1: float, angle_deg: float, length: float) -> tuple[float, float]:
        x2 = x1 + length * math.cos(math.radians(angle_deg))
        y2 = y1 + length * math.sin(math.radians(angle_deg))
        self.line(x1, y1, x2, y2)
        return x2, y2


DrawFn = Callable[[Pen, int, float], None]
"""draw(pen, poles, pole_pitch) -> geometry. ``poles`` > 1 only for spanning symbols."""


@dataclass(frozen=True)
class SymbolDef:
    id: str
    title: str
    length: float
    draw: DrawFn
    category: str = "control"
    spans_poles: bool = False      # drawn once across all poles (motor, PSU)
    terminal_end: bool = False     # no output connection (motor, ground)
    half_width: float = 3.0        # used for label placement
    tags: tuple[str, ...] = field(default_factory=tuple)

    def width_for(self, poles: int, pitch: float) -> float:
        return (poles - 1) * pitch + 2 * self.half_width if self.spans_poles else 2 * self.half_width

    def pole_offsets(self, poles: int, pitch: float) -> list[float]:
        """X offsets of the pole connections relative to the block origin."""
        if not self.spans_poles:
            return [0.0]
        start = -(poles - 1) * pitch / 2
        return [start + i * pitch for i in range(poles)]
