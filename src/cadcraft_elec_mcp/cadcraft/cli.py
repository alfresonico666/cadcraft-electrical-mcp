"""Thin, typed wrapper around the headless ``cadcraft-cli`` executable.

Only stable, documented sub-commands are used (``--version``, ``info``, ``convert``, ``run``).
Every call has a timeout and raises :class:`CadCraftCommandError` with stderr on failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import CadCraftCommandError
from ..logging_setup import get_logger

log = get_logger("cadcraft.cli")

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

Window = tuple[float, float, float, float]


@dataclass(frozen=True)
class CliResult:
    stdout: str
    stderr: str
    returncode: int

    def json_lines(self) -> list[Any]:
        out: list[Any] = []
        for line in self.stdout.splitlines():
            line = line.strip()
            if line.startswith(("{", "[")):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


class CadCraftCli:
    def __init__(self, executable: Path, timeout_s: float = 180.0) -> None:
        self.executable = executable
        self.timeout_s = timeout_s

    # -- low level ---------------------------------------------------------------------------------
    def _run(self, args: Sequence[str], *, timeout_s: float | None = None) -> CliResult:
        cmd = [str(self.executable), *args]
        log.debug("cadcraft-cli %s", " ".join(args))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s or self.timeout_s,
                creationflags=_CREATE_NO_WINDOW,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CadCraftCommandError(f"cadcraft-cli timed out after {exc.timeout}s: {args[:2]}") from exc
        except OSError as exc:
            raise CadCraftCommandError(f"Could not start cadcraft-cli: {exc}") from exc
        result = CliResult(proc.stdout, proc.stderr, proc.returncode)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()[-2000:]
            raise CadCraftCommandError(
                f"cadcraft-cli {' '.join(args[:1])} failed (exit {proc.returncode}): {detail}"
            )
        return result

    @staticmethod
    def _framing(window: Window | None) -> list[str]:
        if window is None:
            return ["--view", "extents"]
        x0, y0, x1, y1 = window
        return ["--window", f"{x0:.3f},{y0:.3f},{x1:.3f},{y1:.3f}"]

    # -- high level --------------------------------------------------------------------------------
    def version(self) -> str:
        return self._run(["--version"], timeout_s=20).stdout.strip()

    def info(self, path: Path) -> dict[str, Any]:
        lines = self._run(["info", str(path), "--compact"]).json_lines()
        if not lines:
            raise CadCraftCommandError(f"cadcraft-cli info returned no JSON for {path}")
        data = lines[0]
        return data if isinstance(data, dict) else {"result": data}

    def convert(self, src: Path, dst: Path, window: Window | None = None) -> Path:
        """DXF/DWG -> DXF/DWG/SVG/PNG/PDF (images show model space)."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        args = ["convert", str(src), str(dst)]
        if dst.suffix.lower() in {".png", ".svg", ".pdf"}:
            args += self._framing(window)
        self._run(args)
        if not dst.is_file():
            raise CadCraftCommandError(f"cadcraft-cli convert did not produce {dst}")
        return dst

    def run_commands(
        self,
        drawing: Path | None,
        commands: Sequence[tuple[str, dict[str, Any]]],
        *,
        save: Path | None = None,
        export: Path | None = None,
        window: Window | None = None,
    ) -> list[Any]:
        """Run engine commands (``--cmd 'id {json}'``) headless; returns one JSON result per command."""
        args: list[str] = ["run"]
        if drawing is not None:
            args.append(str(drawing))
        for command_id, params in commands:
            args += ["--cmd", f"{command_id} {json.dumps(params)}"]
        if save is not None:
            args += ["--save", str(save)]
        if export is not None:
            args += ["--export", str(export), *self._framing(window)]
        return self._run(args).json_lines()

    def run_script(self, drawing: Path | None, script_text: str, save: Path | None = None) -> CliResult:
        args: list[str] = ["run"]
        if drawing is not None:
            args.append(str(drawing))
        args += ["--script", script_text]
        if save is not None:
            args += ["--save", str(save)]
        return self._run(args)

    def plot_window(
        self,
        drawing: Path,
        out: Path,
        window: Window,
        *,
        paper: str = "A3",
        landscape: bool = True,
    ) -> Path:
        """Plot a model-space window to PDF or PNG (white paper, plot lineweights) via ``plot``."""
        device = {".pdf": "CADCraft PDF", ".png": "CADCraft PNG", ".svg": "CADCraft SVG"}.get(
            out.suffix.lower()
        )
        if device is None:
            raise CadCraftCommandError(f"Unsupported plot format: {out.suffix}")
        out.parent.mkdir(parents=True, exist_ok=True)
        x0, y0, x1, y1 = window
        params = {
            "path": str(out),
            "layout": "Model",
            "device": device,
            "paper": paper,
            "landscape": landscape,
            "plotArea": "window",
            "window": [[x0, y0], [x1, y1]],
            "fit": True,
            "lineweights": True,
        }
        self.run_commands(drawing, [("plot", params)])
        if not out.is_file():
            raise CadCraftCommandError(f"CADCraft plot did not produce {out}")
        return out

    def pdf_book(self, drawing: Path, pdf_path: Path, frame_height: float) -> dict[str, Any]:
        """Use CADCraft ``pdfbook``: every closed frame polyline of ``frame_height`` is one PDF page."""
        results = self.run_commands(
            drawing, [("pdfbook", {"path": str(pdf_path), "frameHeight": frame_height})]
        )
        for item in results:
            if isinstance(item, dict) and ("books" in item or "result" in item):
                return item.get("result", item) if "books" not in item else item
        return {"raw": results}
