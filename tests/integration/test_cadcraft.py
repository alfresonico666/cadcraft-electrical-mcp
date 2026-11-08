"""Integration with a real CADCraft installation (skipped when cadcraft-cli is not installed)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from cadcraft_elec_mcp.application import Session
from cadcraft_elec_mcp.application.build import build
from cadcraft_elec_mcp.cadcraft.discovery import find_cli
from cadcraft_elec_mcp.errors import CadCraftNotInstalledError

from ..conftest import make_project

try:
    find_cli()
    HAVE_CADCRAFT = True
except CadCraftNotInstalledError:
    HAVE_CADCRAFT = False

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not HAVE_CADCRAFT, reason="CADCraft not installed")]


def test_full_build_with_cadcraft(session: Session) -> None:
    make_project(session)
    result = build(session, pdf=True, dwg=True, previews=[2])
    files = result["files"]
    assert not [w for w in result["warnings"] if "CADCraft" in w], result["warnings"]
    pdf = Path(files["pdf"])
    assert len(PdfReader(pdf).pages) == len(result["pages"])
    assert Path(files["dwg"]).stat().st_size > 0
    assert Path(files["previews"][0]).read_bytes()[:4] == b"\x89PNG"
    info = session.cadcraft.inspect(Path(files["dxf"]))
    assert info.get("entityCount", 0) > 100
    assert Path(files["cabinet_dxf"]).is_file()
