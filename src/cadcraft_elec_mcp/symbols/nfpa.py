"""NFPA 79 / JIC (IEEE 315) symbol geometry. Symbols not redefined here fall back to IEC shapes."""

from __future__ import annotations

from dataclasses import replace

from . import iec
from .base import Pen, SymbolDef

L = 10.0


def _plates(p: Pen) -> None:
    p.stub_in(-4)
    p.line(-2.2, -4, 2.2, -4)
    p.line(-2.2, -6, 2.2, -6)
    p.stub_out(-6, L)


def contact_no(p: Pen, poles: int, pitch: float) -> None:
    _plates(p)


def contact_nc(p: Pen, poles: int, pitch: float) -> None:
    _plates(p)
    p.line(-2.4, -7.0, 2.4, -3.0)


def _pb_terminals(p: Pen) -> None:
    p.stub_in(-2.8)
    p.circle(0, -3.5, 0.7)
    p.circle(0, -6.5, 0.7)
    p.stub_out(-7.2, L)


def pushbutton_no(p: Pen, poles: int, pitch: float) -> None:
    _pb_terminals(p)
    p.line(-2.2, -2.3, -2.2, -7.7)
    p.line(-2.2, -5.0, -4.5, -5.0)


def pushbutton_nc(p: Pen, poles: int, pitch: float) -> None:
    _pb_terminals(p)
    p.line(-0.7, -2.3, -0.7, -7.7)
    p.line(-0.7, -5.0, -4.5, -5.0)


def estop(p: Pen, poles: int, pitch: float) -> None:
    pushbutton_nc(p, poles, pitch)
    p.arc(-5.5, -5.0, 1.8, 90, 270)
    p.line(-5.5, -3.2, -5.5, -6.8)


def selector(p: Pen, poles: int, pitch: float) -> None:
    _pb_terminals(p)
    p.line(-2.6, -2.6, -0.6, -7.4)
    p.line(-1.6, -5.0, -4.5, -5.0)


def sensor_no(p: Pen, poles: int, pitch: float) -> None:
    _plates(p)
    p.poly([(-5.5, -3.4), (-3.9, -5.0), (-5.5, -6.6), (-7.1, -5.0)], closed=True)


def limit_switch_no(p: Pen, poles: int, pitch: float) -> None:
    _pb_terminals(p)
    p.poly([(0.7, -6.5), (-2.5, -3.0)])
    p.line(-2.5, -3.0, -3.5, -3.0)


def coil(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-2)
    p.circle(0, -5, 3)
    p.stub_out(-8, L)


def coil_valve(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-2)
    p.poly([(0, -2), (-1.5, -2.8), (1.5, -4.0), (-1.5, -5.2), (1.5, -6.4), (0, -8)])  # solenoid loops
    p.stub_out(-8, L)


def lamp(p: Pen, poles: int, pitch: float) -> None:
    coil(p, poles, pitch)
    for dx, dy in ((-3.2, -1.8), (3.2, -1.8), (-3.2, -8.2), (3.2, -8.2)):
        p.line(dx * 0.8, -5 + (dy + 5) * 0.8, dx * 1.15, -5 + (dy + 5) * 1.15)


def mcb(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-2.8)
    p.circle(0, -3.5, 0.7)
    p.circle(0, -6.5, 0.7)
    p.arc(0, -5.0, 2.4, 110, 250)
    p.stub_out(-7.2, L)


def overload(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-3)
    p.poly([(0, -3), (-1.6, -3.6), (-1.6, -6.4), (0, -7)])
    p.stub_out(-7, L)


def motor(p: Pen, poles: int, pitch: float) -> None:
    iec.motor(p, poles, pitch)


_OVERRIDES = {
    "contact_no": contact_no,
    "contact_nc": contact_nc,
    "power_contact": contact_no,
    "pushbutton_no": pushbutton_no,
    "pushbutton_nc": pushbutton_nc,
    "estop": estop,
    "selector": selector,
    "sensor_no": sensor_no,
    "limit_switch_no": limit_switch_no,
    "coil": coil,
    "coil_valve": coil_valve,
    "lamp": lamp,
    "mcb": mcb,
    "mpcb": mcb,
    "overload": overload,
}

SYMBOLS: dict[str, SymbolDef] = {
    sid: (replace(sym, draw=_OVERRIDES[sid]) if sid in _OVERRIDES else sym)
    for sid, sym in iec.SYMBOLS.items()
}
