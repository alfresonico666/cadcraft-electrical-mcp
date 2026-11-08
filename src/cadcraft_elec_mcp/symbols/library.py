"""Creates symbol BLOCK definitions (with ATTDEFs) inside an ezdxf document on demand."""

from __future__ import annotations

from dataclasses import dataclass

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from ..standards import StandardProfile
from .base import LABEL_X, Pen, SymbolDef
from .registry import get_symbol

ATTR_TAG = "TAG"
ATTR_DESC = "DESC"
ATTR_T1 = "T1"
ATTR_T2 = "T2"


@dataclass(frozen=True)
class BlockRef:
    name: str
    symbol: SymbolDef
    poles: int


class SymbolLibrary:
    def __init__(self, doc: Drawing, profile: StandardProfile, pole_pitch: float = 7.5) -> None:
        self.doc = doc
        self.profile = profile
        self.style = profile.symbol_style
        self.pole_pitch = pole_pitch
        self._cache: dict[tuple[str, int, bool], BlockRef] = {}

    def get(self, symbol_id: str) -> SymbolDef:
        return get_symbol(self.style, symbol_id)

    def ensure(self, symbol_id: str, poles: int = 1, *, secondary: bool = False) -> BlockRef:
        """Block for ``symbol_id``. ``secondary`` = extra pole of a multi-pole device (no actuator)."""
        symbol = self.get(symbol_id)
        poles = poles if symbol.spans_poles else 1
        secondary = secondary and not symbol.spans_poles
        key = (symbol_id, poles, secondary)
        if key in self._cache:
            return self._cache[key]
        name = f"ELEC_{self.style.upper()}_{symbol_id.upper()}"
        name += f"_{poles}P" if symbol.spans_poles else ""
        name += "_S" if secondary else ""
        if name not in self.doc.blocks:
            block = self.doc.blocks.new(name, base_point=(0, 0))
            symbol.draw(Pen(block, with_actuator=not secondary), poles, self.pole_pitch)
            self._add_attdefs(block, symbol, poles)
        ref = BlockRef(name, symbol, poles)
        self._cache[key] = ref
        return ref

    def label_x(self, symbol: SymbolDef, poles: int) -> float:
        """X offset (block coordinates) where TAG/DESC texts start."""
        return max(LABEL_X, symbol.width_for(poles, self.pole_pitch) / 2 + 1.5)

    def _add_attdefs(self, block, symbol: SymbolDef, poles: int) -> None:  # type: ignore[no-untyped-def]
        text = self.profile.text
        x_label = self.label_x(symbol, poles)
        mid = -symbol.length / 2

        def attdef(
            tag: str, x: float, y: float, height: float, layer: str, align: TextEntityAlignment
        ) -> None:
            definition = block.add_attdef(
                tag, insert=(x, y), height=height, dxfattribs={"layer": layer, "style": "ELEC"}
            )
            definition.set_placement((x, y), align=align)

        attdef(ATTR_TAG, x_label, mid + 0.8, text.designation, "E-DESIG", TextEntityAlignment.BOTTOM_LEFT)
        attdef(ATTR_DESC, x_label, mid - 0.8, text.general, "E-TEXT", TextEntityAlignment.TOP_LEFT)
        if not symbol.spans_poles:
            attdef(ATTR_T1, -1.0, -0.6, text.terminal, "E-TERMINAL", TextEntityAlignment.TOP_RIGHT)
            if not symbol.terminal_end:
                attdef(
                    ATTR_T2,
                    -1.0,
                    -symbol.length + 0.6,
                    text.terminal,
                    "E-TERMINAL",
                    TextEntityAlignment.BOTTOM_RIGHT,
                )
