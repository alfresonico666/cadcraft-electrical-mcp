"""Runtime settings.

Resolution order (highest first):
1. Environment variables prefixed with ``CADELEC_`` (e.g. ``CADELEC_CONTROL_PORT=7979``).
2. The user config file ``config.toml`` (``%APPDATA%/cadcraft-elec-mcp/config.toml`` on Windows,
   ``~/.config/cadcraft-elec-mcp/config.toml`` elsewhere, or the path in ``CADELEC_CONFIG``).
3. Built-in defaults.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

APP_DIR_NAME = "cadcraft-elec-mcp"


def default_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def default_config_file() -> Path:
    override = os.environ.get("CADELEC_CONFIG")
    return Path(override) if override else default_config_dir() / "config.toml"


def default_workspace() -> Path:
    return Path.home() / "Documents" / "CadElec"


class Settings(BaseSettings):
    """All tunables of the server. See ``docs/CONFIGURATION.md``."""

    model_config = SettingsConfigDict(env_prefix="CADELEC_", extra="ignore")

    # --- CADCraft ------------------------------------------------------------------------------
    cadcraft_cli: Path | None = Field(
        default=None, description="Path to cadcraft-cli.exe. Auto-discovered when empty."
    )
    cadcraft_app: Path | None = Field(
        default=None, description="Path to cadcraft.exe (desktop app). Auto-discovered when empty."
    )
    control_host: str = "127.0.0.1"
    control_port: int = Field(default=7979, ge=1, le=65535)
    cli_timeout_s: float = Field(default=180.0, gt=0)

    # --- Projects and libraries ----------------------------------------------------------------
    workspace_dir: Path = Field(default_factory=default_workspace)
    library_catalogs: list[Path] = Field(
        default_factory=list,
        description="Extra catalog YAML files (e.g. your company devices with local DXF models).",
    )
    library_models_dir: Path | None = Field(
        default=None, description="Where cleaned vendor models are written. Default: <workspace>/library"
    )
    title_block_template: Path | None = Field(
        default=None,
        description="Optional DXF with your company title block; texts like {project_title} are filled.",
    )
    default_profile: Literal["iec", "nfpa"] = "iec"
    font: str = "arial.ttf"

    # --- Misc -----------------------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_file = default_config_file()
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        if toml_file.is_file():
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=toml_file))
        return tuple(sources)

    @property
    def models_dir(self) -> Path:
        return self.library_models_dir or (self.workspace_dir / "library")

    @property
    def log_dir(self) -> Path:
        return self.workspace_dir / "logs"


def load_settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]
