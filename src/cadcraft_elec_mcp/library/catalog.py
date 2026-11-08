"""Device catalog: built-in typical devices + user catalogs (YAML) with local 1:1 front-view models.

Sources, merged in this order (later ids override earlier ones):
1. ``library/data/catalog.yaml`` shipped with the package (generic devices, typical sizes);
2. every file in ``Settings.library_catalogs``;
3. ``<models_dir>/catalog.yaml`` written by ``library_import_model``.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..domain.model import DeviceKind, Mount
from ..errors import LibraryError, NotFoundError
from ..logging_setup import get_logger

log = get_logger("library.catalog")

USER_CATALOG_NAME = "catalog.yaml"


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    manufacturer: str = ""
    part_number: str = ""
    description: str = ""
    kind: DeviceKind = DeviceKind.GENERIC
    mount: Mount = Mount.DIN_RAIL
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    depth_mm: float | None = Field(default=None, gt=0)
    terminals: list[str] = Field(default_factory=list)
    ports: list[str] = Field(default_factory=list)
    io: dict[str, int] = Field(default_factory=dict, description="Channel count, e.g. {DI: 14, DO: 10}")
    io_terminals: dict[str, list[str]] = Field(default_factory=dict)
    model_dxf: str | None = None
    cutout_mm: list[float] | None = Field(default=None, description="Door cut-out [w, h]")
    notes: str = ""
    source: str = Field(default="builtin", exclude=True)

    def matches(self, query: str) -> bool:
        haystack = " ".join(
            [self.id, self.manufacturer, self.part_number, self.description, self.kind.value]
        ).lower()
        return all(token in haystack for token in query.lower().split())


def _read(path: Path, source: str) -> list[CatalogEntry]:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise LibraryError(f"Cannot read catalog {path}: {exc}") from exc
    items = raw.get("devices", []) if isinstance(raw, dict) else raw
    entries: list[CatalogEntry] = []
    for item in items:
        try:
            entry = CatalogEntry.model_validate(item)
        except Exception as exc:
            raise LibraryError(f"Invalid catalog entry in {path}: {item!r}: {exc}") from exc
        entry.source = source
        if entry.model_dxf and not Path(entry.model_dxf).is_absolute():
            entry.model_dxf = str((path.parent / entry.model_dxf).resolve())
        entries.append(entry)
    return entries


class Catalog:
    def __init__(self, extra_files: list[Path] | None = None, models_dir: Path | None = None) -> None:
        self.extra_files = list(extra_files or [])
        self.models_dir = models_dir
        self._entries: dict[str, CatalogEntry] = {}
        self.reload()

    def reload(self) -> None:
        entries: dict[str, CatalogEntry] = {}
        builtin = Path(str(resources.files("cadcraft_elec_mcp.library") / "data" / "catalog.yaml"))
        for entry in _read(builtin, "builtin"):
            entries[entry.id] = entry
        files = list(self.extra_files)
        if self.models_dir is not None and (self.models_dir / USER_CATALOG_NAME).is_file():
            files.append(self.models_dir / USER_CATALOG_NAME)
        for file in files:
            if not file.is_file():
                log.warning("Catalog file not found: %s", file)
                continue
            for entry in _read(file, str(file)):
                entries[entry.id] = entry
        self._entries = entries

    def all(self) -> list[CatalogEntry]:
        return sorted(self._entries.values(), key=lambda e: e.id)

    def get(self, entry_id: str) -> CatalogEntry:
        try:
            return self._entries[entry_id]
        except KeyError as exc:
            raise NotFoundError(f"Catalog entry {entry_id!r} not found.", hint="Use library_search.") from exc

    def search(self, query: str = "", kind: DeviceKind | None = None, limit: int = 50) -> list[CatalogEntry]:
        found = [
            e for e in self.all() if (not query or e.matches(query)) and (kind is None or e.kind is kind)
        ]
        return found[:limit]

    def upsert_user_entry(self, entry: CatalogEntry) -> Path:
        """Add/replace an entry in ``<models_dir>/catalog.yaml``."""
        if self.models_dir is None:
            raise LibraryError("No models directory configured.")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        path = self.models_dir / USER_CATALOG_NAME
        current: list[dict[str, Any]] = []
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            current = list(data.get("devices", []))
        current = [item for item in current if item.get("id") != entry.id]
        current.append(entry.model_dump(mode="json", exclude_none=True, exclude_defaults=False))
        path.write_text(
            yaml.safe_dump({"devices": current}, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        self.reload()
        return path
