"""Cross references (IEC 61082-1): contact -> coil location, and contact mirror under each coil."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ezdxf.layouts import BaseLayout

from ..drawing import add_text

MASTER_SYMBOLS = frozenset({"coil", "coil_valve"})
SLAVE_SYMBOLS = frozenset(
    {"contact_no", "contact_nc", "power_contact", "pushbutton_no", "pushbutton_nc", "estop", "selector"}
)
NC_SYMBOLS = frozenset({"contact_nc", "pushbutton_nc", "estop"})


@dataclass
class XrefItem:
    device: str
    symbol: str
    terminals: list[str]
    ref: str  # "/3.4" (IEC) or "105" (NFPA line)
    anchor: tuple[float, float]  # where to write annotations
    vertical: bool


class CrossRefRegistry:
    def __init__(self) -> None:
        self.items: list[XrefItem] = []

    def add(self, item: XrefItem) -> None:
        self.items.append(item)

    def masters(self) -> dict[str, list[XrefItem]]:
        out: dict[str, list[XrefItem]] = defaultdict(list)
        for item in self.items:
            if item.symbol in MASTER_SYMBOLS:
                out[item.device].append(item)
        return out

    def slaves(self) -> dict[str, list[XrefItem]]:
        out: dict[str, list[XrefItem]] = defaultdict(list)
        for item in self.items:
            if item.symbol in SLAVE_SYMBOLS:
                out[item.device].append(item)
        return out

    def annotate(self, layout: BaseLayout, text_height: float) -> int:
        """Write references; returns how many annotations were placed."""
        masters, slaves = self.masters(), self.slaves()
        count = 0
        for device, contacts in slaves.items():
            if device not in masters:
                continue
            coil_ref = masters[device][0].ref
            for contact in contacts:
                x, y = contact.anchor
                add_text(
                    layout,
                    coil_ref,
                    (x, y),
                    height=text_height,
                    layer="E-XREF",
                    align="TOP_RIGHT" if contact.vertical else "TOP_CENTER",
                )
                count += 1
        for device, coils in masters.items():
            contacts = slaves.get(device, [])
            if not contacts:
                continue
            coil = coils[0]
            x, y = coil.anchor
            step = text_height * 1.5
            for i, contact in enumerate(contacts):
                kind = "NC" if contact.symbol in NC_SYMBOLS else "NO"
                label = f"{' '.join(contact.terminals)} {kind} {contact.ref}"
                add_text(
                    layout,
                    label,
                    (x, y - i * step),
                    height=text_height * 0.8 if text_height > 2.5 else text_height,
                    layer="E-XREF",
                    align="TOP_LEFT",
                )
                count += 1
        return count
