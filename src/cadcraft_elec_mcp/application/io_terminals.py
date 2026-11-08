"""PLC I/O assignment (auto addressing) and terminal strip management."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..domain.designation import natural_key, split_terminal_ref
from ..domain.model import DeviceKind, IoKind, Mount, PlcIoChannel, TerminalSpec
from ..errors import NotFoundError, ProjectError
from .session import Session

_PREFIX = {IoKind.DI: "I", IoKind.DO: "Q"}


class ChannelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: IoKind
    device: str | None = Field(default=None, description="Field device tag (sensor, valve, lamp ...)")
    description: str = ""
    address: str | None = Field(default=None, description="Auto (%I0.0, %Q0.0, %IW64 ...) when empty")
    terminal: str | None = Field(default=None, description="Module terminal; from catalog when empty")
    symbol: str | None = None


def _address(kind: IoKind, index: int, start_byte: int) -> str:
    if kind in _PREFIX:
        return f"%{_PREFIX[kind]}{start_byte + index // 8}.{index % 8}"
    return f"%{'IW' if kind is IoKind.AI else 'QW'}{64 + 2 * index}"  # S7-1200 on-board analog area


def assign_io(session: Session, plc: str, channels: list[ChannelInput]) -> list[dict[str, Any]]:
    project = session.project
    plc_device = project.device(plc)
    if plc_device.kind not in (
        DeviceKind.PLC_CPU,
        DeviceKind.PLC_MODULE,
        DeviceKind.FIELDBUS_COUPLER,
        DeviceKind.IOLINK_MASTER,
        DeviceKind.IOLINK_HUB,
    ):
        raise ProjectError(f"{plc} is a {plc_device.kind.value}, not a PLC/IO module.")
    entry = None
    if plc_device.catalog_id:
        try:
            entry = session.catalog.get(plc_device.catalog_id)
        except NotFoundError:
            entry = None
    created: list[PlcIoChannel] = []
    for item in channels:
        if item.device:
            project.device(item.device)
        existing = [c for c in project.plc_io if c.plc == plc and c.kind is item.kind]
        used_addr = {c.address for c in existing}
        used_term = {c.terminal for c in existing}
        if entry and item.kind.value in entry.io and len(existing) >= entry.io[item.kind.value]:
            raise ProjectError(
                f"{plc} has only {entry.io[item.kind.value]} {item.kind.value} channels.",
                hint="Add an expansion module (plc_module) and assign to it.",
            )
        index = 0
        start = int(plc_device.data.get(f"{item.kind.value.lower()}_start_byte", "0"))
        address = item.address
        if address is None:
            while _address(item.kind, index, start) in used_addr:
                index += 1
            address = _address(item.kind, index, start)
        terminal = item.terminal
        if terminal is None:
            names = entry.io_terminals.get(item.kind.value, []) if entry else []
            free = [n for n in names if n not in used_term]
            terminal = free[0] if free else f"{item.kind.value}{len(existing)}"
        channel = PlcIoChannel(
            plc=plc,
            address=address,
            kind=item.kind,
            terminal=terminal,
            device=item.device,
            symbol=item.symbol,
            description=item.description,
        )
        project.plc_io.append(channel)
        created.append(channel)
    project.plc_io.sort(key=lambda c: (c.plc, natural_key(c.address)))
    session.commit()
    return [c.model_dump(mode="json", exclude_defaults=True) for c in created]


def remove_io(session: Session, plc: str, address: str) -> dict[str, str]:
    project = session.project
    before = len(project.plc_io)
    project.plc_io = [
        c for c in project.plc_io if not (c.plc == plc and c.address.upper() == address.upper())
    ]
    if len(project.plc_io) == before:
        raise NotFoundError(f"No channel {address} on {plc}.")
    session.commit()
    return {"removed": f"{plc} {address}"}


def list_io(session: Session, plc: str | None = None) -> list[dict[str, Any]]:
    return [
        c.model_dump(mode="json", exclude_defaults=True)
        for c in session.project.plc_io
        if plc is None or c.plc == plc
    ]


# -- terminal strips ----------------------------------------------------------------------------------
def _ensure_strip_device(session: Session, tag: str | None, description: str) -> str:
    project = session.project
    if tag is None:
        tag = session.profile.allocate_tag(DeviceKind.TERMINAL_STRIP, [d.tag for d in project.devices])
    if not project.has_device(tag):
        from ..domain.model import Device

        project.add_device(
            Device(tag=tag, kind=DeviceKind.TERMINAL_STRIP, description=description, mount=Mount.DIN_RAIL)
        )
    project.get_or_create_strip(tag, description)
    return tag


def _next_number(numbers: set[str]) -> str:
    n = 1
    while str(n) in numbers:
        n += 1
    return str(n)


def add_terminals(
    session: Session,
    strip: str | None,
    description: str,
    count: int = 0,
    numbers: list[str] | None = None,
    potential: str | None = None,
    pe: bool = False,
) -> dict[str, Any]:
    tag = _ensure_strip_device(session, strip, description)
    model = session.project.strip(tag)
    used = {t.number for t in model.terminals}
    new_numbers = list(numbers or [])
    for _ in range(count):
        number = _next_number(used | set(new_numbers))
        new_numbers.append(number)
    for number in new_numbers:
        if number in used:
            raise ProjectError(f"{tag}:{number} already exists.")
        model.terminals.append(TerminalSpec(number=number, potential=potential, pe=pe))
        used.add(number)
    model.terminals.sort(key=lambda t: natural_key(t.number))
    session.commit()
    return {"strip": tag, "terminals": [t.number for t in model.terminals]}


def assign_io_terminals(
    session: Session, strip: str | None, plc: str | None = None, description: str = "Señales de campo"
) -> dict[str, Any]:
    """Give every field-mounted I/O device its own terminal on ``strip`` (created if needed)."""
    project = session.project
    tag = _ensure_strip_device(session, strip, description)
    model = project.strip(tag)
    used = {t.number for t in model.terminals}
    assigned: list[str] = []
    for channel in project.plc_io:
        if plc and channel.plc != plc:
            continue
        if channel.strip_terminal or not channel.device:
            continue
        if project.device(channel.device).mount is not Mount.FIELD:
            continue
        number = _next_number(used)
        used.add(number)
        model.terminals.append(
            TerminalSpec(number=number, internal=f"{channel.plc}:{channel.terminal}", external=channel.device)
        )
        channel.strip_terminal = f"{tag}:{number}"
        assigned.append(f"{channel.address} -> {tag}:{number}")
    model.terminals.sort(key=lambda t: natural_key(t.number))
    session.commit()
    return {"strip": tag, "assigned": assigned}


def list_strips(session: Session) -> list[dict[str, Any]]:
    return [s.model_dump(mode="json", exclude_defaults=True) for s in session.project.terminal_strips]


def remove_terminal(session: Session, ref: str) -> dict[str, str]:
    strip, number = split_terminal_ref(ref)
    model = session.project.strip(strip)
    model.terminals = [t for t in model.terminals if t.number != number]
    for channel in session.project.plc_io:
        if channel.strip_terminal == ref:
            channel.strip_terminal = None
    session.commit()
    return {"removed": ref}
