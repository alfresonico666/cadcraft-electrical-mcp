"""Project persistence: one YAML file per project, written atomically.

Layout on disk::

    <workspace>/<project_code>/<project_code>.elec.yaml   <- source of truth (put it in git)
    <workspace>/<project_code>/output/                     <- generated DXF/PDF/PNG/XLSX
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..domain.model import SCHEMA_VERSION, Project
from ..errors import NotFoundError, ProjectError

SUFFIX = ".elec.yaml"
_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_name(text: str) -> str:
    cleaned = _SAFE.sub("_", text).strip(" .")
    if not cleaned:
        raise ProjectError(f"Invalid project code {text!r}.")
    return cleaned


class ProjectStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def project_dir(self, code: str) -> Path:
        return self.workspace / safe_name(code)

    def project_file(self, code: str) -> Path:
        return self.project_dir(code) / f"{safe_name(code)}{SUFFIX}"

    def output_dir(self, code: str) -> Path:
        path = self.project_dir(code) / "output"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_projects(self) -> list[dict[str, str]]:
        if not self.workspace.is_dir():
            return []
        out = []
        for file in sorted(self.workspace.glob(f"*/*{SUFFIX}")):
            out.append({"code": file.name[: -len(SUFFIX)], "path": str(file)})
        return out

    def exists(self, code: str) -> bool:
        return self.project_file(code).is_file()

    def resolve(self, code_or_path: str) -> Path:
        candidate = Path(code_or_path)
        if candidate.suffix in {".yaml", ".yml"} and candidate.is_file():
            return candidate
        path = self.project_file(code_or_path)
        if path.is_file():
            return path
        raise NotFoundError(
            f"Project {code_or_path!r} not found in {self.workspace}.",
            hint="Use project_list or pass the full path of the .elec.yaml file.",
        )

    @staticmethod
    def load(path: Path) -> Project:
        try:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProjectError(f"Cannot read {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ProjectError(f"{path} is not a project file.")
        version = raw.get("schema_version", SCHEMA_VERSION)
        if version > SCHEMA_VERSION:
            raise ProjectError(
                f"{path} uses schema v{version}; this server supports v{SCHEMA_VERSION}.",
                hint="Update cadcraft-elec-mcp.",
            )
        try:
            return Project.model_validate(raw)
        except ValidationError as exc:
            raise ProjectError(f"Invalid project file {path}:\n{exc}") from exc

    @staticmethod
    def save(project: Project, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = project.model_dump(mode="json", exclude_defaults=False)
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110)
        fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            os.replace(tmp, path)
        except OSError as exc:
            Path(tmp).unlink(missing_ok=True)
            raise ProjectError(f"Cannot write {path}: {exc}") from exc
        return path
