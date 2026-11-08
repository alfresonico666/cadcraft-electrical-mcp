"""End-to-end example: the 26HA076 LVDT machine (S7-1200 + KTP400 + Balluff IO-Link + Keyence GT2).

It uses the same application layer the MCP tools call, so it doubles as an integration test and as
documentation of a complete workflow.

    python examples/build_26ha076.py --workspace C:/temp/CadElec --models "C:/.../Modelos" [--profile nfpa]

``--models`` is optional: when given, the vendor front views are cleaned and used in the cabinet layout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cadcraft_elec_mcp.application import Session, cabinet, devices, io_terminals, network, projects, sheets
from cadcraft_elec_mcp.application import build as build_uc
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
    Protocol,
    SheetKind,
    TitleBlockInfo,
)
from cadcraft_elec_mcp.library import CatalogEntry, import_model

VENDOR_MODELS = {  # catalog id -> (relative path in the Modelos folder, kind, mount)
    "siemens-6es7214-1ag40-0xb0": "Siemens - PLC/PLC_Terminales.dxf",
    "balluff-bni00hl": "Balluff - Master Hub - BNI00HL/Ethernet_MasterHub.dxf",
    "balluff-bni007z": "Balluff - Expand Hub - BNI007Z/ExpandClean.dxf",
    "balluff-bni0067": "Balluff - Switcher 8 Puertos - BNI0067/FrontViewSwitcher.dxf",
    "siemens-6av2123-2db03-0ax0": "Siemens - HMI - KTP400/6av21232db030ax0_front.dwg",
}


def import_vendor_models(session: Session, models: Path) -> None:
    for catalog_id, relative in VENDOR_MODELS.items():
        src = models / relative
        if not src.is_file():
            print(f"  (skip) {src} not found")
            continue
        base = session.catalog.get(catalog_id)
        report = import_model(
            src, session.settings.models_dir / f"{catalog_id}.dxf", cadcraft=session.cadcraft
        )
        entry = base.model_copy(
            update={"model_dxf": str(report.path), "width_mm": report.width_mm, "height_mm": report.height_mm}
        )
        session.catalog.upsert_user_entry(CatalogEntry.model_validate(entry.model_dump()))
        print(f"  model {catalog_id}: {report.width_mm} x {report.height_mm} mm")


def tag_of(session: Session, description: str) -> str:
    return next(d.tag for d in session.project.devices if d.description == description)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--models", type=Path)
    parser.add_argument("--profile", default="iec")
    args = parser.parse_args()

    session = Session(Settings(workspace_dir=args.workspace))
    if args.models:
        import_vendor_models(session, args.models)

    info = TitleBlockInfo(
        project_code="26HA076",
        project_title="Máquina LVDT",
        machine="Estación de medición LVDT",
        client="Cliente automotriz",
        plant="Planta",
        company="Mi Empresa",
        author="A. Castillo",
        reviewer="Revisor",
        revision="A",
    )
    projects.create_project(session, info, args.profile, None, overwrite=True)

    D = DeviceInput  # noqa: N806 - short alias for readability
    devices.add_devices(
        session,
        [
            D(
                kind=DeviceKind.MAIN_SWITCH,
                description="Interruptor general",
                catalog_id="generic-main-switch",
            ),
            D(catalog_id="generic-mcb-2p", description="Protección fuente 24 VDC"),
            D(catalog_id="generic-mcb-2p", description="Protección PC / monitor"),
            D(catalog_id="generic-psu-24v-10a"),
            D(catalog_id="generic-mcb-1p", description="Protección PLC"),
            D(catalog_id="generic-mcb-1p", description="Protección HMI / switch"),
            D(catalog_id="generic-mcb-1p", description="Protección IO-Link / Keyence"),
            D(catalog_id="generic-mcb-1p", description="Protección actuadores"),
            D(catalog_id="siemens-6es7214-1ag40-0xb0"),
            D(catalog_id="siemens-6av2123-2db03-0ax0"),
            D(catalog_id="balluff-bni0067"),
            D(catalog_id="balluff-bni00hl"),
            D(catalog_id="balluff-bni007z"),
            D(catalog_id="keyence-dl-pn1", width_mm=22.4, height_mm=90),
            D(catalog_id="generic-safety-relay", description="Relé de seguridad paro de emergencia"),
            D(catalog_id="generic-relay-2co", description="Habilitación válvulas"),
            D(kind=DeviceKind.ESTOP, description="Paro de emergencia", mount=Mount.DOOR),
            D(kind=DeviceKind.PUSHBUTTON, description="Rearme seguridad", mount=Mount.DOOR),
            D(kind=DeviceKind.PUSHBUTTON, description="Inicio de ciclo", mount=Mount.FIELD),
            D(kind=DeviceKind.SENSOR, description="Sensor presencia pieza", mount=Mount.FIELD),
            D(kind=DeviceKind.SENSOR, description="Limit switch A - Empuje X", mount=Mount.FIELD),
            D(kind=DeviceKind.SENSOR, description="Limit switch A - Empuje Y", mount=Mount.FIELD),
            D(kind=DeviceKind.SENSOR, description="Limit switch A - Clamp Z", mount=Mount.FIELD),
            D(catalog_id="smc-sy7320-5dz-02", description="Electroválvula Empuje X"),
            D(catalog_id="smc-sy7320-5dz-02", description="Electroválvula Empuje Y"),
            D(catalog_id="smc-sy7320-5dz-02", description="Electroválvula Clamp Z"),
            D(catalog_id="smc-sy7320-5dz-02", description="Electroválvula Marcaje"),
            D(kind=DeviceKind.PILOT_LAMP, description="Piloto máquina lista", mount=Mount.DOOR),
            D(catalog_id="generic-service-port-rj45"),
            D(kind=DeviceKind.PC, description="PC industrial + monitor", mount=Mount.FIELD),
            D(catalog_id="keyence-gt2-500", description="Sensor GT2 Datum Z", mount=Mount.FIELD),
        ],
    )
    t = lambda d: tag_of(session, d)  # noqa: E731
    plc = t("S7-1200 CPU 1214C DC/DC/DC")
    psu = t("Fuente 24 VDC 10 A")

    P = PathElement  # noqa: N806
    sheets.add_sheet(
        session,
        SheetKind.POWER,
        "Distribución AC",
        sheet_id="ac",
        paths=[
            CircuitPath(
                label="Alimentación fuente 24 VDC",
                supply=["L1", "N"],
                pe=True,
                elements=[
                    P(device=t("Interruptor general")),
                    P(device=t("Protección fuente 24 VDC")),
                    P(device=psu),
                ],
            ),
            CircuitPath(
                label="PC industrial / monitor",
                supply=["L1", "N"],
                pe=True,
                elements=[
                    P(device=t("Interruptor general")),
                    P(device=t("Protección PC / monitor")),
                    P(device=t("PC industrial + monitor"), symbol="device_box"),
                ],
            ),
        ],
    )
    sheets.add_sheet(
        session,
        SheetKind.CONTROL,
        "Distribución 24 VDC y seguridad",
        sheet_id="dc",
        paths=[
            CircuitPath(
                label="PLC 1L+",
                supply=["24V"],
                elements=[P(device=t("Protección PLC")), P(device=plc, symbol="device_box")],
            ),
            CircuitPath(
                label="HMI y switch",
                supply=["24V"],
                elements=[
                    P(device=t("Protección HMI / switch")),
                    P(device=t('HMI KTP400 Basic 4" PN'), symbol="device_box"),
                ],
            ),
            CircuitPath(
                label="IO-Link master / DL-PN1",
                supply=["24V"],
                elements=[
                    P(device=t("Protección IO-Link / Keyence")),
                    P(device=t("IO-Link master PROFINET 8 puertos (BNI00HL)"), symbol="device_box"),
                ],
            ),
            CircuitPath(
                label="Paro de emergencia",
                supply=["24V"],
                return_rail="0V",
                elements=[
                    P(device=t("Paro de emergencia")),
                    P(device=t("Rearme seguridad")),
                    P(device=t("Relé de seguridad paro de emergencia")),
                ],
            ),
            CircuitPath(
                label="Habilitación válvulas",
                supply=["24V"],
                return_rail="0V",
                elements=[P(device=t("Protección actuadores")), P(device=t("Habilitación válvulas"))],
            ),
            CircuitPath(
                label="Piloto máquina lista",
                supply=["24V"],
                return_rail="0V",
                elements=[
                    P(device=t("Habilitación válvulas"), symbol="contact_no"),
                    P(device=t("Piloto máquina lista")),
                ],
            ),
        ],
    )

    io_terminals.assign_io(
        session,
        plc,
        [
            ChannelInput(kind=IoKind.DI, device=t("Sensor presencia pieza"), description="Pieza presente"),
            ChannelInput(kind=IoKind.DI, device=t("Limit switch A - Empuje X"), description="Empuje X atrás"),
            ChannelInput(kind=IoKind.DI, device=t("Limit switch A - Empuje Y"), description="Empuje Y atrás"),
            ChannelInput(kind=IoKind.DI, device=t("Limit switch A - Clamp Z"), description="Clamp Z abierto"),
            ChannelInput(kind=IoKind.DI, device=t("Inicio de ciclo"), description="Inicio de ciclo"),
            ChannelInput(kind=IoKind.DO, device=t("Electroválvula Empuje X"), description="Empuje X"),
            ChannelInput(kind=IoKind.DO, device=t("Electroválvula Empuje Y"), description="Empuje Y"),
            ChannelInput(kind=IoKind.DO, device=t("Electroválvula Clamp Z"), description="Clamp Z"),
            ChannelInput(kind=IoKind.DO, device=t("Electroválvula Marcaje"), description="Marcaje"),
        ],
    )
    io_terminals.add_terminals(session, None, "Alimentación", numbers=["L1", "N"])
    io_terminals.add_terminals(session, None, "Tierra", numbers=["PE1", "PE2"], pe=True)
    io_terminals.assign_io_terminals(session, None)
    sheets.add_sheet(session, SheetKind.PLC_IO, "E/S PLC", sheet_id="plc-io", plc=plc)

    switch = t("Switch Ethernet industrial 8 puertos (BNI0067)")
    master = t("IO-Link master PROFINET 8 puertos (BNI00HL)")
    network.add_links(
        session,
        [
            NetworkLink(a_device=plc, a_port="X1P1", b_device=switch, b_port="P1", cable="-WG1"),
            NetworkLink(
                a_device=switch, a_port="P2", b_device=t('HMI KTP400 Basic 4" PN'), b_port="X1", cable="-WG2"
            ),
            NetworkLink(a_device=switch, a_port="P3", b_device=master, b_port="X01", cable="-WG3"),
            NetworkLink(
                a_device=switch,
                a_port="P4",
                b_device=t("Unidad de comunicación PROFINET (sensores GT2)"),
                b_port="PN1",
                cable="-WG4",
            ),
            NetworkLink(
                a_device=switch, a_port="P5", b_device=t("Puerto de servicio RJ45 en puerta"), cable="-WG5"
            ),
            NetworkLink(a_device=switch, a_port="P6", b_device=t("PC industrial + monitor"), cable="-WG6"),
            NetworkLink(
                a_device=master,
                a_port="Port0",
                b_device=t("IO-Link hub (BNI007Z)"),
                b_port="IOL",
                protocol=Protocol.IOLINK,
                cable="-WG7",
            ),
        ],
    )
    sheets.add_sheet(session, SheetKind.NETWORK, "Red PROFINET / IO-Link", sheet_id="net")

    # 500x400 Spacial CRN with 25x40 slim ducts (small enclosure)
    cabinet.configure(
        session,
        {
            "enclosure_catalog_id": "schneider-nsycrn54250p",
            "plate_width": 350,
            "plate_height": 450,
            "duct_width": 25,
            "duct_depth": 40,
            "duct_clearance": 5,
        },
    )

    print(json.dumps(build_uc.build(session, previews=list(range(1, 12))), indent=1, ensure_ascii=False))
    print(json.dumps(build_uc.run_validation(session).to_dict(), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
