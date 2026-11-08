"""Domain exception hierarchy.

Every error raised by this package derives from :class:`CadElecError`, so the MCP layer can turn
it into a clean tool error with a stable ``code`` the model (and a human) can act on.
"""

from __future__ import annotations


class CadElecError(Exception):
    """Base class for all errors of this package."""

    code: str = "error"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict[str, str]:
        data = {"code": self.code, "message": self.message}
        if self.hint:
            data["hint"] = self.hint
        return data

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}" + (f" (hint: {self.hint})" if self.hint else "")


class ConfigError(CadElecError):
    code = "config"


class ProjectError(CadElecError):
    code = "project"


class NoActiveProjectError(ProjectError):
    code = "no_active_project"

    def __init__(self) -> None:
        super().__init__(
            "No project is open.", hint="Call project_create or project_open first."
        )


class NotFoundError(ProjectError):
    code = "not_found"


class DuplicateError(ProjectError):
    code = "duplicate"


class DesignationError(CadElecError):
    code = "designation"


class StandardsError(CadElecError):
    code = "standards"


class SymbolError(CadElecError):
    code = "symbol"


class LibraryError(CadElecError):
    code = "library"


class LayoutError(CadElecError):
    code = "layout"


class GenerationError(CadElecError):
    code = "generation"


class CadCraftError(CadElecError):
    code = "cadcraft"


class CadCraftNotInstalledError(CadCraftError):
    code = "cadcraft_not_installed"


class CadCraftCommandError(CadCraftError):
    code = "cadcraft_command"


class CadCraftConnectionError(CadCraftError):
    code = "cadcraft_connection"
