"""Application session: settings + collaborators + the currently open project.

Every mutating use case calls :meth:`Session.commit` so the YAML on disk is always current
(the MCP server can be restarted at any time without losing work).
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from ..cadcraft import CadCraftService
from ..config import Settings
from ..domain.model import Project
from ..errors import NoActiveProjectError
from ..library import Catalog
from ..persistence import ProjectStore
from ..standards import StandardProfile, load_profile


class Session:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.workspace_dir)
        self._project: Project | None = None
        self._path: Path | None = None

    @cached_property
    def catalog(self) -> Catalog:
        return Catalog(self.settings.library_catalogs, self.settings.models_dir)

    @cached_property
    def cadcraft(self) -> CadCraftService:
        return CadCraftService(self.settings)

    # -- project lifecycle ------------------------------------------------------------------------
    @property
    def has_project(self) -> bool:
        return self._project is not None

    @property
    def project(self) -> Project:
        if self._project is None:
            raise NoActiveProjectError()
        return self._project

    @property
    def path(self) -> Path:
        if self._path is None:
            raise NoActiveProjectError()
        return self._path

    @property
    def profile(self) -> StandardProfile:
        return load_profile(self.project.profile)

    @property
    def output_dir(self) -> Path:
        out = self.path.parent / "output"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def activate(self, project: Project, path: Path) -> None:
        self._project = project
        self._path = path

    def commit(self) -> Path:
        return self.store.save(self.project, self.path)
