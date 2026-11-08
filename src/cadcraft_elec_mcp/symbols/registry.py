"""Which symbol represents a device, and which terminal names it gets (IEC 60947 / IEC 60445)."""

from __future__ import annotations

from collections import defaultdict

from ..domain.model import DeviceKind, SheetKind
from ..errors import SymbolError
from . import iec, nfpa
from .base import SymbolDef

_STYLES: dict[str, dict[str, SymbolDef]] = {"iec": iec.SYMBOLS, "nfpa": nfpa.SYMBOLS}

_CONTROL_DEFAULTS: dict[DeviceKind, str] = {
    DeviceKind.CONTACTOR: "coil",
    DeviceKind.RELAY: "coil",
    DeviceKind.TIMER_RELAY: "coil",
    DeviceKind.SAFETY_RELAY: "box",
    DeviceKind.MCB: "mcb",
    DeviceKind.MPCB: "mpcb",
    DeviceKind.FUSE: "fuse",
    DeviceKind.MAIN_SWITCH: "disconnector",
    DeviceKind.OVERLOAD: "contact_nc",
    DeviceKind.PUSHBUTTON: "pushbutton_no",
    DeviceKind.ESTOP: "estop",
    DeviceKind.SELECTOR: "selector",
    DeviceKind.PILOT_LAMP: "lamp",
    DeviceKind.SENSOR: "sensor_no",
    DeviceKind.PRESSURE_SENSOR: "sensor_no",
    DeviceKind.MEASURING_SENSOR: "sensor_no",
    DeviceKind.SAFETY_SENSOR: "box",
    DeviceKind.SOLENOID_VALVE: "coil_valve",
    DeviceKind.VALVE_MANIFOLD: "coil_valve",
    DeviceKind.TERMINAL_STRIP: "terminal",
    DeviceKind.CONNECTOR: "terminal",
    DeviceKind.MOTOR: "motor",
    DeviceKind.PSU: "psu",
    DeviceKind.FAN: "motor",
}

_POWER_DEFAULTS: dict[DeviceKind, str] = {
    **_CONTROL_DEFAULTS,
    DeviceKind.CONTACTOR: "power_contact",
    DeviceKind.OVERLOAD: "overload",
}

_SPANNING_FALLBACK = "device_box"


def symbols_for_style(style: str) -> dict[str, SymbolDef]:
    try:
        return _STYLES[style]
    except KeyError as exc:
        raise SymbolError(f"Unknown symbol style {style!r}") from exc


def get_symbol(style: str, symbol_id: str) -> SymbolDef:
    table = symbols_for_style(style)
    if symbol_id not in table:
        raise SymbolError(
            f"Unknown symbol {symbol_id!r}.", hint=f"Available: {', '.join(sorted(table))}"
        )
    return table[symbol_id]


def default_symbol(kind: DeviceKind, sheet_kind: SheetKind) -> str:
    table = _POWER_DEFAULTS if sheet_kind is SheetKind.POWER else _CONTROL_DEFAULTS
    return table.get(kind, "box" if sheet_kind is not SheetKind.POWER else _SPANNING_FALLBACK)


class TerminalAllocator:
    """Assigns terminal names when the user did not give them.

    * coil/valve: A1-A2 · lamp: X1-X2 · power poles: 1-2, 3-4, 5-6
    * auxiliary contacts: NO = n3-n4, NC = n1-n2 with n = running contact number per device
    * overload auxiliary: 95-96 (NC), 97-98 (NO) · sensors: 1 (BN) - 4 (BK) · motor: U1 V1 W1
    """

    def __init__(self) -> None:
        self._aux_seq: dict[str, int] = defaultdict(int)

    def reserve(self, device: str, terminals: list[list[str]]) -> None:
        """Register explicit terminals so auto numbering skips used sequence numbers."""
        for pair in terminals:
            for name in pair:
                if len(name) == 2 and name.isdigit() and name[1] in "1234":
                    self._aux_seq[device] = max(self._aux_seq[device], int(name[0]))

    def allocate(self, device: str, kind: DeviceKind, symbol_id: str, poles: int) -> list[list[str]]:
        if symbol_id in {"coil", "coil_valve"}:
            return [["A1", "A2"]]
        if symbol_id == "lamp":
            return [["X1", "X2"]]
        if symbol_id in {"sensor_no", "limit_switch_no"} and kind in {
            DeviceKind.SENSOR, DeviceKind.PRESSURE_SENSOR, DeviceKind.MEASURING_SENSOR
        }:
            return [["1", "4"]]
        if symbol_id == "motor":
            names = ["U1", "V1", "W1"] if poles >= 3 else ["L", "N"][:poles]
            return [[n, ""] for n in names]
        if symbol_id in {"psu", "device_box"}:
            names = ["L1", "L2", "L3"] if poles >= 3 else ["L", "N"][:poles]
            return [[n, ""] for n in names]
        if symbol_id in {"contact_no", "contact_nc"} and kind in {DeviceKind.OVERLOAD, DeviceKind.MPCB}:
            return [["95", "96"]] if symbol_id == "contact_nc" else [["97", "98"]]
        if symbol_id in {"power_contact", "mcb", "mpcb", "fuse", "disconnector", "overload"}:
            return [[str(2 * i + 1), str(2 * i + 2)] for i in range(poles)]
        if symbol_id in {"contact_no", "contact_nc", "pushbutton_no", "pushbutton_nc", "estop", "selector",
                         "sensor_no", "limit_switch_no"}:
            self._aux_seq[device] += 1
            n = self._aux_seq[device]
            no = symbol_id in {"contact_no", "pushbutton_no", "selector", "sensor_no", "limit_switch_no"}
            return [[f"{n}3", f"{n}4"]] if no else [[f"{n}1", f"{n}2"]]
        return [[str(2 * i + 1), str(2 * i + 2)] for i in range(poles)]
