"""Tabular reports derived from the project + netlist (pure functions -> list of rows)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from ..domain.designation import natural_key
from ..domain.model import DeviceKind, Project
from ..generators.context import Wire
from ..generators.terminal_plan import terminal_rows


@dataclass
class Table:
    name: str
    columns: list[str]
    rows: list[list[object]]

    def as_dicts(self) -> list[dict[str, object]]:
        return [dict(zip(self.columns, row, strict=False)) for row in self.rows]


def bill_of_materials(project: Project) -> Table:
    groups: OrderedDict[tuple[str, str, str], list[str]] = OrderedDict()
    meta: dict[tuple[str, str, str], tuple[str, str]] = {}
    for device in sorted(project.devices, key=lambda d: (d.kind.value, natural_key(d.tag))):
        if device.kind is DeviceKind.TERMINAL_STRIP:
            continue
        key = (device.manufacturer, device.part_number or f"({device.kind.value})", device.description)
        groups.setdefault(key, []).append(device.tag)
        meta[key] = (device.kind.value, device.mount.value)
    rows: list[list[object]] = []
    for pos, (key, tags) in enumerate(groups.items(), start=1):
        manufacturer, part, description = key
        kind, mount = meta[key]
        rows.append([pos, len(tags), ", ".join(tags), description, manufacturer, part, kind, mount])
    for strip in project.terminal_strips:
        rows.append(
            [
                len(rows) + 1,
                len(strip.terminals),
                strip.tag,
                f"Bornes {strip.description}".strip(),
                "",
                "(borne de paso)",
                "terminal_strip",
                "din_rail",
            ]
        )
    return Table(
        "BOM",
        [
            "Pos",
            "Cant/Qty",
            "Designaciones/Tags",
            "Descripción",
            "Fabricante",
            "Número de parte",
            "Tipo",
            "Montaje",
        ],
        rows,
    )


def wire_list(wires: list[Wire]) -> Table:
    rows: list[list[object]] = [
        [w.number, w.from_ref, w.to_ref, w.color_code, w.cross_section_mm2, w.potential or "", w.ref]
        for w in sorted(wires, key=lambda w: (w.sheet, natural_key(w.number)))
    ]
    return Table(
        "Cables",
        ["Hilo/Wire", "Desde/From", "Hasta/To", "Color", "Sección mm²", "Potencial", "Referencia"],
        rows,
    )


def terminal_list(project: Project, wires: list[Wire]) -> Table:
    rows: list[list[object]] = []
    for strip in project.terminal_strips:
        for row in terminal_rows(project, strip, wires):
            rows.append(
                [
                    row.strip,
                    row.number,
                    row.internal,
                    row.internal_wire,
                    row.external,
                    row.external_wire,
                    row.potential,
                    row.color,
                ]
            )
    return Table(
        "Bornes",
        [
            "Bornera",
            "Borne",
            "Destino interno",
            "Hilo int.",
            "Destino externo",
            "Hilo ext.",
            "Potencial",
            "Color",
        ],
        rows,
    )


def io_list(project: Project) -> Table:
    rows: list[list[object]] = []
    for ch in sorted(project.plc_io, key=lambda c: (c.plc, natural_key(c.address))):
        device = project.device(ch.device) if ch.device and project.has_device(ch.device) else None
        rows.append(
            [
                ch.plc,
                ch.address,
                ch.kind.value,
                ch.terminal,
                ch.device or "",
                ch.description or (device.description if device else ""),
                ch.strip_terminal or "",
            ]
        )
    return Table(
        "E-S PLC",
        ["PLC", "Dirección", "Tipo", "Borne PLC", "Dispositivo", "Descripción", "Borne bornera"],
        rows,
    )


def network_list(project: Project) -> Table:
    rows: list[list[object]] = [
        [
            link.cable or "",
            link.protocol.value,
            link.a_device,
            link.a_port,
            link.b_device,
            link.b_port,
            link.length_m or "",
        ]
        for link in project.network
    ]
    return Table(
        "Red", ["Cable", "Protocolo", "Equipo A", "Puerto A", "Equipo B", "Puerto B", "Longitud m"], rows
    )


def all_tables(project: Project, wires: list[Wire]) -> list[Table]:
    return [
        bill_of_materials(project),
        wire_list(wires),
        terminal_list(project, wires),
        io_list(project),
        network_list(project),
    ]
