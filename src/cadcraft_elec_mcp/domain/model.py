"""Electrical project model (pure data, no I/O).

The project YAML is the single source of truth: drawings, reports and validation are all derived
from it, so regenerating is idempotent and the file can be versioned in git.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..errors import DuplicateError, NotFoundError
from .designation import natural_key

SCHEMA_VERSION = 1


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


class DeviceKind(StrEnum):
    CONTACTOR = "contactor"
    RELAY = "relay"
    SAFETY_RELAY = "safety_relay"
    TIMER_RELAY = "timer_relay"
    MCB = "mcb"
    MPCB = "mpcb"
    FUSE = "fuse"
    RCD = "rcd"
    MAIN_SWITCH = "main_switch"
    OVERLOAD = "overload"
    PSU = "psu"
    TRANSFORMER = "transformer"
    PLC_CPU = "plc_cpu"
    PLC_MODULE = "plc_module"
    HMI = "hmi"
    NETWORK_SWITCH = "network_switch"
    IOLINK_MASTER = "iolink_master"
    IOLINK_HUB = "iolink_hub"
    FIELDBUS_COUPLER = "fieldbus_coupler"
    SENSOR = "sensor"
    PRESSURE_SENSOR = "pressure_sensor"
    MEASURING_SENSOR = "measuring_sensor"
    SAFETY_SENSOR = "safety_sensor"
    SOLENOID_VALVE = "solenoid_valve"
    VALVE_MANIFOLD = "valve_manifold"
    MOTOR = "motor"
    VFD = "vfd"
    PUSHBUTTON = "pushbutton"
    ESTOP = "estop"
    SELECTOR = "selector"
    PILOT_LAMP = "pilot_lamp"
    TERMINAL_STRIP = "terminal_strip"
    CONNECTOR = "connector"
    SERVICE_PORT = "service_port"
    FAN = "fan"
    CABLE = "cable"
    PC = "pc"
    GENERIC = "generic"


class Mount(StrEnum):
    DIN_RAIL = "din_rail"
    BACKPLATE = "backplate"
    DOOR = "door"
    FIELD = "field"


class PotentialKind(StrEnum):
    AC_PHASE = "ac_phase"
    AC_NEUTRAL = "ac_neutral"
    PE = "pe"
    AC_CONTROL = "ac_control"
    DC_PLUS = "dc_plus"
    DC_MINUS = "dc_minus"
    EXTERNAL = "external"


class SheetKind(StrEnum):
    COVER = "cover"
    POWER = "power"
    CONTROL = "control"
    PLC_IO = "plc_io"
    NETWORK = "network"
    TERMINAL_PLAN = "terminal_plan"
    CABINET_LAYOUT = "cabinet_layout"


class IoKind(StrEnum):
    DI = "DI"
    DO = "DO"
    AI = "AI"
    AQ = "AQ"


class Protocol(StrEnum):
    PROFINET = "profinet"
    ETHERNET = "ethernet"
    IOLINK = "iolink"
    PROFISAFE = "profisafe"


# ------------------------------------------------------------------------------------------------
class TitleBlockInfo(_Model):
    project_code: str = Field(description="Project number, e.g. 26HA076")
    project_title: str = ""
    machine: str = ""
    client: str = ""
    plant: str = ""
    company: str = ""
    author: str = ""
    reviewer: str = ""
    revision: str = "A"
    date: str = Field(default_factory=lambda: date.today().isoformat())
    description: str = ""


class Device(_Model):
    tag: str = Field(description="Designation shown on drawings, e.g. -KF1 (IEC) or CR1 (NFPA)")
    kind: DeviceKind
    description: str = ""
    manufacturer: str = ""
    part_number: str = ""
    catalog_id: str | None = None
    function: str | None = Field(default=None, description="IEC 81346 function aspect, e.g. A1")
    location: str | None = Field(default=None, description="IEC 81346 location aspect, e.g. CAB1")
    mount: Mount = Mount.DIN_RAIL
    terminals: list[str] = Field(default_factory=list)
    ports: list[str] = Field(default_factory=list, description="Network ports, e.g. X1P1, X1P2")
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    depth_mm: float | None = Field(default=None, gt=0)
    model_dxf: str | None = Field(default=None, description="Cleaned 1:1 front-view DXF for layouts")
    data: dict[str, str] = Field(default_factory=dict)

    @field_validator("tag")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("tag must not be empty")
        return value


class Potential(_Model):
    name: str = Field(description="L1, L2, L3, N, PE, 24V, 0V, L1_CTRL ...")
    kind: PotentialKind
    voltage: str = ""
    source: str | None = Field(default=None, description="Where it is generated, e.g. -TB1:+")


class PathElement(_Model):
    device: str = Field(description="Device tag (must exist in the project)")
    symbol: str | None = Field(
        default=None, description="Symbol id; default depends on the device kind and sheet kind"
    )
    terminals: list[list[str]] | None = Field(
        default=None,
        description="Per pole [in, out] terminal names. Auto-assigned (IEC 60947 numbering) if empty.",
    )
    label: str | None = Field(default=None, description="Extra text next to the symbol")


class CircuitPath(_Model):
    label: str = ""
    supply: list[str] = Field(
        min_length=1, description="Rail potential per pole, e.g. ['L1','L2','L3'] or ['24V']"
    )
    elements: list[PathElement] = Field(default_factory=list)
    return_rail: str | None = Field(default=None, description="Bottom rail, e.g. 0V or N")
    pe: bool = Field(default=False, description="Connect the last element to the PE rail")
    column: int | None = Field(default=None, ge=1, description="Force a column (1-based)")


class SheetSpec(_Model):
    id: str
    kind: SheetKind
    title: str
    paths: list[CircuitPath] = Field(default_factory=list)
    plc: str | None = Field(default=None, description="plc_io: PLC/module tag to draw")
    io_kinds: list[IoKind] = Field(default_factory=list, description="plc_io: which channels")
    note: str = ""


class PlcIoChannel(_Model):
    plc: str = Field(description="CPU/module tag")
    address: str = Field(description="%I0.0, %Q0.1, %IW64 ...")
    kind: IoKind
    terminal: str = Field(description="Module terminal, e.g. DIa.0 / .0 / 0")
    device: str | None = Field(default=None, description="Field device tag")
    symbol: str | None = None
    description: str = ""
    strip_terminal: str | None = Field(default=None, description="e.g. -XD2:5 (auto when empty)")


class NetworkLink(_Model):
    a_device: str
    a_port: str = ""
    b_device: str
    b_port: str = ""
    protocol: Protocol = Protocol.PROFINET
    cable: str | None = None
    length_m: float | None = Field(default=None, gt=0)


class TerminalSpec(_Model):
    number: str
    potential: str | None = None
    internal: str | None = Field(default=None, description="Cabinet side, e.g. -KF1:%I0.0 or -QA1:2")
    external: str | None = Field(default=None, description="Field side, e.g. -BG1:4")
    wire: str | None = None
    pe: bool = False


class TerminalStrip(_Model):
    tag: str
    description: str = ""
    terminals: list[TerminalSpec] = Field(default_factory=list)


class RailSpec(_Model):
    devices: list[str] = Field(default_factory=list, description="Device tags left to right")


class Placement(_Model):
    x: float
    y: float


class CabinetSpec(_Model):
    enclosure_catalog_id: str | None = None
    enclosure_width: float = Field(default=500, gt=0)
    enclosure_height: float = Field(default=400, gt=0)
    enclosure_depth: float = Field(default=250, gt=0)
    plate_width: float = Field(default=450, gt=0)
    plate_height: float = Field(default=350, gt=0)
    plate_margin: float = Field(default=15, ge=0)
    duct_width: float = Field(default=40, gt=0)
    duct_depth: float = Field(default=60, gt=0)
    vertical_ducts: bool = True
    duct_clearance: float = Field(default=10, ge=0, description="Gap device <-> wire duct")
    device_gap: float = Field(default=0, ge=0, description="Gap between DIN-rail devices")
    rails: list[RailSpec] = Field(
        default_factory=list, description="Explicit rail contents; auto-filled when empty"
    )
    placements: dict[str, Placement] = Field(
        default_factory=dict, description="Manual position (lower-left, plate coords) per tag"
    )
    door_devices: list[str] = Field(default_factory=list)
    spare_ratio: float = Field(default=0.2, ge=0, le=0.9)


Tag = Annotated[str, Field(min_length=1)]


class Project(_Model):
    schema_version: int = SCHEMA_VERSION
    info: TitleBlockInfo
    profile: str = "iec"
    devices: list[Device] = Field(default_factory=list)
    potentials: list[Potential] = Field(default_factory=list)
    sheets: list[SheetSpec] = Field(default_factory=list)
    plc_io: list[PlcIoChannel] = Field(default_factory=list)
    network: list[NetworkLink] = Field(default_factory=list)
    terminal_strips: list[TerminalStrip] = Field(default_factory=list)
    cabinet: CabinetSpec | None = None

    # -- devices -------------------------------------------------------------------------------
    def device(self, tag: str) -> Device:
        for dev in self.devices:
            if dev.tag == tag:
                return dev
        raise NotFoundError(f"Device {tag!r} not found.", hint="Use device_list to see tags.")

    def has_device(self, tag: str) -> bool:
        return any(dev.tag == tag for dev in self.devices)

    def add_device(self, device: Device) -> Device:
        if self.has_device(device.tag):
            raise DuplicateError(f"Device {device.tag!r} already exists.")
        self.devices.append(device)
        self.devices.sort(key=lambda d: natural_key(d.tag))
        return device

    def remove_device(self, tag: str) -> Device:
        dev = self.device(tag)
        self.devices.remove(dev)
        return dev

    def devices_of(self, *kinds: DeviceKind) -> list[Device]:
        return [d for d in self.devices if d.kind in kinds]

    # -- potentials ----------------------------------------------------------------------------
    def potential(self, name: str) -> Potential | None:
        return next((p for p in self.potentials if p.name == name), None)

    def upsert_potential(self, potential: Potential) -> Potential:
        self.potentials = [p for p in self.potentials if p.name != potential.name] + [potential]
        return potential

    # -- sheets --------------------------------------------------------------------------------
    def sheet(self, sheet_id: str) -> SheetSpec:
        for sheet in self.sheets:
            if sheet.id == sheet_id:
                return sheet
        raise NotFoundError(f"Sheet {sheet_id!r} not found.", hint="Use sheet_list.")

    # -- terminal strips -----------------------------------------------------------------------
    def strip(self, tag: str) -> TerminalStrip:
        for strip in self.terminal_strips:
            if strip.tag == tag:
                return strip
        raise NotFoundError(f"Terminal strip {tag!r} not found.")

    def get_or_create_strip(self, tag: str, description: str = "") -> TerminalStrip:
        for strip in self.terminal_strips:
            if strip.tag == tag:
                return strip
        strip = TerminalStrip(tag=tag, description=description)
        self.terminal_strips.append(strip)
        return strip
