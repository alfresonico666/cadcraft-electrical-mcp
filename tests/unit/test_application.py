"""Use cases + generation pipeline without CADCraft (pure DXF)."""

from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from cadcraft_elec_mcp.application import Session, devices, io_terminals, projects
from cadcraft_elec_mcp.application.build import compile_project, run_validation
from cadcraft_elec_mcp.application.devices import DeviceInput
from cadcraft_elec_mcp.application.io_terminals import ChannelInput
from cadcraft_elec_mcp.domain.model import DeviceKind, IoKind, NetworkLink
from cadcraft_elec_mcp.errors import DuplicateError, ProjectError
from cadcraft_elec_mcp.persistence import ProjectStore
from cadcraft_elec_mcp.reports import all_tables, to_xlsx

from ..conftest import make_project


def test_project_is_persisted_and_reloadable(session: Session, project_tags: dict[str, str]) -> None:
    path = session.path
    assert path.is_file()
    reloaded = ProjectStore.load(path)
    assert reloaded == session.project
    assert projects.open_project(session, "T001")["counts"]["devices"] == len(reloaded.devices)


def test_duplicate_project_requires_overwrite(session: Session, project_tags: dict[str, str]) -> None:
    with pytest.raises(DuplicateError):
        projects.create_project(session, session.project.info, "iec", None)


def test_tags_follow_profile(session: Session, project_tags: dict[str, str]) -> None:
    assert project_tags["Motor contactor"] == "-QA1"
    assert project_tags["Run relay"] == "-KF1"
    assert project_tags["Part present"] == "-BG1"


def test_rename_updates_references(session: Session, project_tags: dict[str, str]) -> None:
    devices.update_device(session, "-KF1", {"tag": "-KF9"})
    control = session.project.sheet("control")
    assert {e.device for p in control.paths for e in p.elements} >= {"-KF9"}


def test_remove_referenced_device_needs_force(session: Session, project_tags: dict[str, str]) -> None:
    with pytest.raises(ProjectError):
        devices.remove_device(session, "-KF1")
    devices.remove_device(session, "-KF1", force=True)
    assert not session.project.has_device("-KF1")


def test_io_autoaddress_and_capacity(session: Session, project_tags: dict[str, str]) -> None:
    plc = project_tags["S7-1200 CPU 1214C DC/DC/DC"]
    channels = {c.address: c.terminal for c in session.project.plc_io}
    assert channels == {"%I0.0": "DIa.0", "%Q0.0": "DQa.0"}
    io_terminals.assign_io(session, plc, [ChannelInput(kind=IoKind.DI) for _ in range(13)])
    with pytest.raises(ProjectError):
        io_terminals.assign_io(session, plc, [ChannelInput(kind=IoKind.DI)])
    assert any(c.address == "%I1.5" for c in session.project.plc_io)


def test_compile_builds_all_sheets(session: Session, project_tags: dict[str, str], tmp_path: Path) -> None:
    compiled = compile_project(session)
    kinds = [p.kind for p in compiled.ctx.pages]
    assert kinds[0] == "cover"
    assert {"power", "control", "plc_io", "network", "terminal_plan", "cabinet_layout"} <= set(kinds)
    # cross reference contact -> coil registered
    assert "-KF1" in compiled.ctx.xrefs.masters()
    assert "-KF1" in compiled.ctx.xrefs.slaves()
    # netlist: rail wires carry the potential name, PE wire exists
    numbers = {w.number for w in compiled.ctx.wires}
    assert {"L1", "24V", "0V", "PE"} <= numbers
    out = tmp_path / "set.dxf"
    compiled.ctx.doc.saveas(out)
    doc = ezdxf.readfile(out)
    auditor = doc.audit()
    assert not auditor.has_errors
    assert "TITLE_BLOCK" in doc.blocks
    assert "E-WIRE-DC_PLUS" in doc.layers


def test_reports_and_validation(session: Session, project_tags: dict[str, str], tmp_path: Path) -> None:
    compiled = compile_project(session)
    tables = {t.name: t for t in all_tables(session.project, compiled.ctx.wires)}
    assert tables["E-S PLC"].rows and tables["Cables"].rows and tables["BOM"].rows
    terminals = tables["Bornes"].as_dicts()
    field_row = next(r for r in terminals if r["Destino externo"] == project_tags["Part present"])
    assert field_row["Destino interno"].endswith("DIa.0")
    assert to_xlsx(list(tables.values()), tmp_path / "lists.xlsx").is_file()
    report = run_validation(session, compiled)
    assert report.ok, report.to_dict()


def test_validation_catches_conflicts(session: Session, project_tags: dict[str, str]) -> None:
    plc = project_tags["S7-1200 CPU 1214C DC/DC/DC"]
    io_terminals.assign_io(session, plc, [ChannelInput(kind=IoKind.DI, address="%I0.0", terminal="DIa.7")])
    session.project.network.append(NetworkLink(a_device=plc, a_port="X1P1", b_device=plc, b_port="X1P2"))
    report = run_validation(session).to_dict()
    rules = {i["rule"] for i in report["issues"] if i["severity"] == "error"}
    assert {"plc_io_conflicts", "network_ports"} <= rules


@pytest.mark.parametrize("profile", ["nfpa", "iec_legacy"])
def test_other_profiles_compile(settings, profile: str) -> None:  # type: ignore[no-untyped-def]
    session = Session(settings)
    tags = make_project(session, profile)
    assert tags["Run relay"] == ("CR1" if profile == "nfpa" else "-K2")
    compiled = compile_project(session)
    assert len(compiled.ctx.pages) >= 6
    assert run_validation(session, compiled).ok


def test_terminal_strip_device_kind(session: Session, project_tags: dict[str, str]) -> None:
    strips = [d for d in session.project.devices if d.kind is DeviceKind.TERMINAL_STRIP]
    assert strips and session.project.terminal_strips[0].terminals
    io_terminals.add_terminals(session, strips[0].tag, "", count=2)
    with pytest.raises(ProjectError):
        io_terminals.add_terminals(session, strips[0].tag, "", numbers=["1"])
    devices.add_devices(session, [DeviceInput(kind=DeviceKind.TERMINAL_STRIP, description="Spare")])
