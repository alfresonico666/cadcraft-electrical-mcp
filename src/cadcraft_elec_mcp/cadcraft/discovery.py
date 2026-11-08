"""Locate the CADCraft executables on this machine."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from ..errors import CadCraftNotInstalledError

CLI_NAME = "cadcraft-cli.exe" if sys.platform == "win32" else "cadcraft-cli"
APP_NAME = "cadcraft.exe" if sys.platform == "win32" else "cadcraft"


def _registry_install_dirs() -> list[Path]:
    if sys.platform != "win32":
        return []
    import winreg  # Windows only

    dirs: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, r"Software\CADCraft") as key:
                value, _ = winreg.QueryValueEx(key, "InstallDir")
                dirs.append(Path(value))
        except OSError:
            continue
    return dirs


def candidate_dirs() -> list[Path]:
    dirs = _registry_install_dirs()
    if sys.platform == "win32":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                dirs += [Path(base) / "CADCraft", Path(base) / "ArtCraft" / "CADCraft"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs += [Path(local) / "Programs" / "ArtCraft" / "CADCraft", Path(local) / "Programs" / "CADCraft"]
    return dirs


def _find(executable: str, explicit: Path | None) -> Path:
    if explicit is not None:
        if explicit.is_file():
            return explicit
        raise CadCraftNotInstalledError(
            f"Configured CADCraft path does not exist: {explicit}",
            hint="Fix CADELEC_CADCRAFT_CLI / cadcraft_cli in config.toml.",
        )
    on_path = shutil.which(executable)
    if on_path:
        return Path(on_path)
    for directory in candidate_dirs():
        candidate = directory / executable
        if candidate.is_file():
            return candidate
    raise CadCraftNotInstalledError(
        f"{executable} not found.",
        hint="Install CADCraft (https://github.com/storytold/cadcraft/releases) or set cadcraft_cli in "
        "config.toml.",
    )


def find_cli(explicit: Path | None = None) -> Path:
    return _find(CLI_NAME, explicit)


def find_app(explicit: Path | None = None, cli_path: Path | None = None) -> Path:
    if explicit is None and cli_path is not None and (cli_path.parent / APP_NAME).is_file():
        return cli_path.parent / APP_NAME
    return _find(APP_NAME, explicit)
