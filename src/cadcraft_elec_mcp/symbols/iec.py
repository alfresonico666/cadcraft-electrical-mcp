"""IEC 60617 symbol geometry (simplified, drawn on a 2.5 mm grid, 10 mm standard length)."""

from __future__ import annotations

import math

from .base import Pen, SymbolDef

L = 10.0  # standard symbol length


# --- contacts ----------------------------------------------------------------------------------------
def _contact_no(p: Pen) -> None:
    p.stub_in(-3)
    p.line(0, -7, -2.6, -2.4)  # moving contact (blade), open
    p.stub_out(-7, L)


def _contact_nc(p: Pen) -> None:
    p.stub_in(-3)
    p.line(0, -3, -2.2, -3)  # fixed contact hook
    p.line(0, -7, -2.9, -2.4)  # blade resting past the hook
    p.stub_out(-7, L)


def _actuator(p: Pen, y: float = -4.8, x_blade: float = -1.3) -> float | None:
    """Dashed mechanical link from the blade to the left; returns the actuator x position.

    Returns ``None`` on secondary poles (the operating means is drawn once, on the first pole).
    """
    if not p.with_actuator:
        return None
    p.line(x_blade, y, -6.0, y, linetype="DASHED")
    return -6.0


def contact_no(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)


def contact_nc(p: Pen, poles: int, pitch: float) -> None:
    _contact_nc(p)


def power_contact(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    p.arc(0, -3.0, 0.9, 180, 360)  # contactor function (semicircle) at the fixed contact


def disconnector(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    p.line(-1.0, -3.0, 1.0, -3.0)  # isolating function bar
    x = _actuator(p)
    if x is None:
        return
    p.line(x, -3.8, x, -5.8)


def mcb(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    p.line(-0.8, -2.2, 0.8, -3.8)  # circuit-breaker function (X)
    p.line(-0.8, -3.8, 0.8, -2.2)
    x = _actuator(p)
    if x is None:
        return
    p.rect(x - 2.0, -6.0, x, -3.6)  # thermal-magnetic release


def mpcb(p: Pen, poles: int, pitch: float) -> None:
    mcb(p, poles, pitch)
    if p.with_actuator:
        p.text(-7.0, -8.2, "I>", 1.8)


def pushbutton_no(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    x = _actuator(p)
    if x is None:
        return
    p.poly([(x + 1.0, -3.3), (x, -3.3), (x, -6.3), (x + 1.0, -6.3)])


def pushbutton_nc(p: Pen, poles: int, pitch: float) -> None:
    _contact_nc(p)
    x = _actuator(p, x_blade=-1.6)
    if x is None:
        return
    p.poly([(x + 1.0, -3.3), (x, -3.3), (x, -6.3), (x + 1.0, -6.3)])


def estop(p: Pen, poles: int, pitch: float) -> None:
    _contact_nc(p)
    x = _actuator(p, x_blade=-1.6)
    if x is None:
        return
    p.arc(x - 0.2, -4.8, 2.0, 90, 270)  # mushroom head
    p.line(x - 0.2, -2.8, x - 0.2, -6.8)


def selector(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    x = _actuator(p)
    if x is None:
        return
    p.poly([(x + 0.8, -3.4), (x, -3.4), (x, -6.2), (x - 0.8, -6.2)])


def sensor_no(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    x = _actuator(p)
    if x is None:
        return
    cx = x - 1.6
    p.poly([(cx, -3.2), (cx + 1.6, -4.8), (cx, -6.4), (cx - 1.6, -4.8)], closed=True)  # proximity
    p.line(cx - 0.8, -4.8, cx + 0.8, -4.8)


def limit_switch_no(p: Pen, poles: int, pitch: float) -> None:
    _contact_no(p)
    if p.with_actuator:
        p.poly([(-1.3, -4.8), (-3.0, -4.8), (-3.8, -3.8)])


# --- coils, loads ------------------------------------------------------------------------------------
def coil(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-3)
    p.rect(-3.0, -3.0, 3.0, -7.0)
    p.stub_out(-7, L)


def coil_valve(p: Pen, poles: int, pitch: float) -> None:
    coil(p, poles, pitch)
    p.line(-3.0, -7.0, 3.0, -3.0)  # electromechanical actuator for valves
    if p.with_actuator:
        p.poly([(-5.5, -3.8), (-4.0, -3.8), (-4.0, -6.2), (-5.5, -6.2)])


def lamp(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-2)
    p.circle(0, -5, 3)
    d = 3 * math.cos(math.radians(45))
    p.line(-d, -5 - d, d, -5 + d)
    p.line(-d, -5 + d, d, -5 - d)
    p.stub_out(-8, L)


def fuse(p: Pen, poles: int, pitch: float) -> None:
    p.line(0, 0, 0, -L)
    p.rect(-1.5, -2.0, 1.5, -8.0)


def overload(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-2.5)
    p.rect(-2.2, -2.5, 2.2, -7.5)
    p.poly([(0, -2.5), (0, -3.8), (1.2, -3.8), (1.2, -6.2), (0, -6.2), (0, -7.5)])
    p.stub_out(-7.5, L)


def terminal(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-1.5)
    p.circle(0, -2.5, 1.0)
    p.stub_out(-3.5, 5.0)


def box(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-2)
    p.rect(-4.0, -2.0, 4.0, -8.0)
    p.stub_out(-8, L)


def pe_ground(p: Pen, poles: int, pitch: float) -> None:
    p.stub_in(-3)
    p.line(-3.0, -3.0, 3.0, -3.0)
    p.line(-2.0, -4.0, 2.0, -4.0)
    p.line(-1.0, -5.0, 1.0, -5.0)


# --- spanning symbols (one body across all poles) -----------------------------------------------------
def motor(p: Pen, poles: int, pitch: float) -> None:
    radius = max(6.0, (poles - 1) * pitch / 2 + 2.5)
    cy = -radius
    for i in range(poles):
        x = -(poles - 1) * pitch / 2 + i * pitch
        y = cy + math.sqrt(max(radius**2 - x**2, 0.0))
        p.line(x, 0, x, y)
    p.circle(0, cy, radius)
    p.text(0, cy + 1.2, "M", 3.5)
    p.text(0, cy - 2.6, "3~" if poles >= 3 else ("1~" if poles == 2 else "="), 2.5)


def psu(p: Pen, poles: int, pitch: float) -> None:
    half = max(6.0, (poles - 1) * pitch / 2 + 4)
    for i in range(poles):
        x = -(poles - 1) * pitch / 2 + i * pitch
        p.line(x, 0, x, -2)
    p.rect(-half, -2, half, -14)
    p.line(-half, -14, half, -2)
    p.text(-half / 2, -7.5, "~", 3.0)
    p.text(half / 2, -11.5, "=", 3.0)


def device_box(p: Pen, poles: int, pitch: float) -> None:
    half = max(5.0, (poles - 1) * pitch / 2 + 4)
    for i in range(poles):
        x = -(poles - 1) * pitch / 2 + i * pitch
        p.line(x, 0, x, -2)
    p.rect(-half, -2, half, -12)


SYMBOLS: dict[str, SymbolDef] = {
    s.id: s
    for s in [
        SymbolDef("contact_no", "Contacto NA", L, contact_no),
        SymbolDef("contact_nc", "Contacto NC", L, contact_nc),
        SymbolDef("power_contact", "Contacto principal de contactor", L, power_contact, "power"),
        SymbolDef("disconnector", "Seccionador / interruptor principal", L, disconnector, "power"),
        SymbolDef("mcb", "Interruptor magnetotérmico", L, mcb, "power"),
        SymbolDef("mpcb", "Guardamotor", L, mpcb, "power"),
        SymbolDef("pushbutton_no", "Pulsador NA", L, pushbutton_no),
        SymbolDef("pushbutton_nc", "Pulsador NC", L, pushbutton_nc),
        SymbolDef("estop", "Paro de emergencia (NC, enclavamiento)", L, estop),
        SymbolDef("selector", "Selector", L, selector),
        SymbolDef("sensor_no", "Sensor de proximidad (NA)", L, sensor_no),
        SymbolDef("limit_switch_no", "Final de carrera (NA)", L, limit_switch_no),
        SymbolDef("coil", "Bobina (relé / contactor)", L, coil, half_width=3.0),
        SymbolDef("coil_valve", "Bobina de electroválvula", L, coil_valve, half_width=3.0),
        SymbolDef("lamp", "Piloto / lámpara", L, lamp),
        SymbolDef("fuse", "Fusible", L, fuse, "power", half_width=1.5),
        SymbolDef("overload", "Relé térmico", L, overload, "power"),
        SymbolDef("terminal", "Borne", 5.0, terminal, half_width=1.0),
        SymbolDef("box", "Dispositivo genérico", L, box, half_width=4.0),
        SymbolDef("pe_ground", "Tierra de protección", 5.0, pe_ground, terminal_end=True),
        SymbolDef(
            "motor", "Motor", 15.0, motor, "power", spans_poles=True, terminal_end=True, half_width=6.0
        ),
        SymbolDef(
            "psu",
            "Fuente de alimentación AC/DC",
            14.0,
            psu,
            "power",
            spans_poles=True,
            terminal_end=True,
            half_width=6.0,
        ),
        SymbolDef(
            "device_box",
            "Equipo (caja)",
            12.0,
            device_box,
            spans_poles=True,
            terminal_end=True,
            half_width=5.0,
        ),
    ]
}
