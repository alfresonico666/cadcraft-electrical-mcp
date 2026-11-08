from __future__ import annotations

from pathlib import Path

import pytest

from cadcraft_elec_mcp.application import Session, devices, io_terminals, network, projects, sheets
from cadcraft_elec_mcp.application.devices import DeviceInput
from cadcraft_elec_mcp.application.io_terminals import ChannelInput
from cadcraft_elec_mcp.config import Settings
from cadcraft_elec_mcp.domain.model import (
    CircuitPath,
    DeviceKind,
    IoKind,
    Mount,
    NetworkLink,
    PathElement,
    SheetKind,
    TitleBlockInfo,
)


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("CADELEC_CONFIG", str(tmp_path / "no-config.toml"))
    return Settings(workspace_dir=tmp_path / "ws")


@pytest.fixture
def session(settings: Settings) -> Session:
    return Session(settings)


def make_project(session: Session, profile: str = "iec") -> dict[str, str]:
    """Small but complete project: power, control with relay contacts, PLC I/O, network, cabinet."""
    projects.create_project(session, TitleBlockInfo(project_code="T001", project_title="Test"), profile, None)
    added = devices.add_devices(
        session,
        [
            DeviceInput(kind=DeviceKind.MAIN_SWITCH, description="Main"),
            DeviceInput(catalog_id="generic-mcb-3p", description="Motor MCB"),
            DeviceInput(catalog_id="generic-contactor-9a", description="Motor contactor"),
            DeviceInput(kind=DeviceKind.MOTOR, description="Pump", mount=Mount.FIELD),
            DeviceInput(catalog_id="generic-psu-24v-5a"),
            DeviceInput(kind=DeviceKind.PUSHBUTTON, description="Start", mount=Mount.DOOR),
            DeviceInput(catalog_id="generic-relay-2co", description="Run relay"),
            DeviceInput(catalog_id="siemens-6es7214-1ag40-0xb0"),
            DeviceInput(kind=DeviceKind.SENSOR, description="Part present", mount=Mount.FIELD),
            DeviceInput(catalog_id="smc-sy7320-5dz-02", description="Clamp valve"),
            DeviceInput(catalog_id="balluff-bni0067"),
        ],
    )
    tags = {d["description"]: d["tag"] for d in added}
    sheets.add_sheet(
        session,
        SheetKind.POWER,
        "Power",
        sheet_id="power",
        paths=[
            CircuitPath(
                label="Pump",
                supply=["L1", "L2", "L3"],
                pe=True,
                elements=[
                    PathElement(device=tags["Main"]),
                    PathElement(device=tags["Motor MCB"]),
                    PathElement(device=tags["Motor contactor"]),
                    PathElement(device=tags["Pump"]),
                ],
            ),
            CircuitPath(
                label="PSU", supply=["L1", "N"], elements=[PathElement(device=tags["Fuente 24 VDC 5 A"])]
            ),
        ],
    )
    sheets.add_sheet(
        session,
        SheetKind.CONTROL,
        "Control",
        sheet_id="control",
        paths=[
            CircuitPath(
                label="Run",
                supply=["24V"],
                return_rail="0V",
                elements=[PathElement(device=tags["Start"]), PathElement(device=tags["Run relay"])],
            ),
            CircuitPath(
                label="Contactor",
                supply=["24V"],
                return_rail="0V",
                elements=[
                    PathElement(device=tags["Run relay"], symbol="contact_no"),
                    PathElement(device=tags["Motor contactor"]),
                ],
            ),
        ],
    )
    plc = tags["S7-1200 CPU 1214C DC/DC/DC"]
    io_terminals.assign_io(
        session,
        plc,
        [
            ChannelInput(kind=IoKind.DI, device=tags["Part present"], description="Part"),
            ChannelInput(kind=IoKind.DO, device=tags["Clamp valve"], description="Clamp"),
        ],
    )
    io_terminals.assign_io_terminals(session, None)
    sheets.add_sheet(session, SheetKind.PLC_IO, "PLC I/O", sheet_id="io", plc=plc)
    switch = tags["Switch Ethernet industrial 8 puertos (BNI0067)"]
    network.add_links(session, [NetworkLink(a_device=plc, a_port="X1P1", b_device=switch, b_port="P1")])
    sheets.add_sheet(session, SheetKind.NETWORK, "Network", sheet_id="net")
    from cadcraft_elec_mcp.application import cabinet

    cabinet.configure(
        session, {"plate_width": 600, "plate_height": 600, "enclosure_width": 650, "enclosure_height": 650}
    )
    return tags


@pytest.fixture
def project_tags(session: Session) -> dict[str, str]:
    return make_project(session)
