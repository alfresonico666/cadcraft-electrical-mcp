"""Facade used by the application layer: everything CADCraft can do *for* us.

Generation of drawings happens in Python (ezdxf); CADCraft is used to
- validate that the DXF opens (``info``),
- render previews (PNG), produce PDFs (single sheets or multi-page books) and DWG,
- convert vendor DWG models to DXF,
- show results in the running desktop app (control port) when available.
"""

from __future__ import annotations

import subprocess
import sys
from functools import cached_property
from pathlib import Path
from typing import Any

from pypdf import PdfWriter

from ..config import Settings
from ..errors import CadCraftConnectionError, CadCraftError
from ..logging_setup import get_logger
from .cli import CadCraftCli, Window
from .control import ControlClient
from .discovery import find_app, find_cli

log = get_logger("cadcraft.service")

ISO_A_HEIGHTS = {"A0": 841.0, "A1": 594.0, "A2": 420.0, "A3": 297.0, "A4": 210.0}


class CadCraftService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def cli(self) -> CadCraftCli:
        return CadCraftCli(find_cli(self.settings.cadcraft_cli), timeout_s=self.settings.cli_timeout_s)

    @cached_property
    def control(self) -> ControlClient:
        return ControlClient(self.settings.control_host, self.settings.control_port)

    # -- status ----------------------------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {"control_port": self.settings.control_port}
        try:
            info["cli"] = str(self.cli.executable)
            info["version"] = self.cli.version()
        except CadCraftError as exc:
            info["cli_error"] = exc.to_dict()
        info["app_connected"] = self.control.is_available()
        return info

    # -- outputs ---------------------------------------------------------------------------------------
    def inspect(self, dxf: Path) -> dict[str, Any]:
        return self.cli.info(dxf)

    def preview_png(self, dxf: Path, png: Path, window: Window, paper: str, landscape: bool = True) -> Path:
        return self.cli.plot_window(dxf, png, window, paper=paper, landscape=landscape)

    def sheets_pdf(
        self, dxf: Path, pdf: Path, windows: list[Window], paper: str, sheet_height: float
    ) -> Path:
        """Multi-page PDF. ISO A papers use ``pdfbook`` (one call); other papers plot + merge."""
        pdf.parent.mkdir(parents=True, exist_ok=True)
        if paper in ISO_A_HEIGHTS and abs(ISO_A_HEIGHTS[paper] - sheet_height) < 0.5:
            result = self.cli.pdf_book(dxf, pdf, sheet_height)
            if pdf.is_file():
                log.info("pdfbook: %s", result)
                return pdf
            log.warning("pdfbook produced no file (%s); falling back to per-sheet plot", result)
        parts: list[Path] = []
        for index, window in enumerate(windows, start=1):
            part = pdf.with_name(f"{pdf.stem}.part{index:03d}.pdf")
            parts.append(self.cli.plot_window(dxf, part, window, paper=paper, landscape=True))
        writer = PdfWriter()
        for part in parts:
            writer.append(str(part))
        with pdf.open("wb") as handle:
            writer.write(handle)
        for part in parts:
            part.unlink(missing_ok=True)
        return pdf

    def to_dwg(self, dxf: Path, dwg: Path) -> Path:
        return self.cli.convert(dxf, dwg)

    def dwg_to_dxf(self, dwg: Path, dxf: Path) -> Path:
        return self.cli.convert(dwg, dxf)

    # -- live desktop app ------------------------------------------------------------------------------
    def open_in_app(self, path: Path, launch_if_needed: bool = True) -> dict[str, Any]:
        if self.control.is_available():
            self.control.open(path)
            return {"opened": str(path), "via": "control_port"}
        if not launch_if_needed:
            raise CadCraftConnectionError(
                "CADCraft desktop app is not running with a control port.",
                hint=f"Run: cadcraft --control {self.settings.control_port}",
            )
        app = find_app(self.settings.cadcraft_app, self.cli.executable)
        flags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        subprocess.Popen(
            [str(app), str(path), "--control", str(self.settings.control_port)],
            creationflags=flags,
            close_fds=True,
        )
        return {"opened": str(path), "via": "launched_app", "control_port": self.settings.control_port}

    def execute(self, command: str, params: dict[str, Any]) -> Any:
        return self.control.execute(command, params)
