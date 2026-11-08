"""Clean vendor 2D models (PARTcommunity/CADENAS, Siemens, Keyence ...) into 1:1 mm front views.

Cleaning steps:
* DWG -> DXF through CADCraft (``cadcraft-cli convert``);
* drop ATTDEF/ATTRIB (CADENAS metadata), POINT entities, ``*ConnectionPoints*`` layers and,
  optionally, dimensions and texts (vendor sheet annotations);
* scale to millimetres (explicit ``scale``, ``target_width_mm`` or $INSUNITS) and move the lower-left
  corner of the extents to (0, 0);
* write ``<models_dir>/<id>.dxf`` (R2018) and register it in the user catalog.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from ezdxf import bbox, recover
from ezdxf.addons.importer import Importer
from ezdxf.document import Drawing
from ezdxf.math import Matrix44

from ..cadcraft.service import CadCraftService
from ..errors import LibraryError
from ..logging_setup import get_logger

log = get_logger("library.importer")

_INCH = 1
_MM = 4
_DROP_TYPES = {"ATTDEF", "ATTRIB", "POINT"}
_ANNOTATION_TYPES = {"DIMENSION", "LEADER", "MULTILEADER", "TOLERANCE", "ARC_DIMENSION"}
_TEXT_TYPES = {"TEXT", "MTEXT"}
_DROP_LAYER = re.compile(r"connection\s*points?", re.IGNORECASE)


@dataclass
class ImportReport:
    path: Path
    width_mm: float
    height_mm: float
    scale: float
    source_units: int
    kept: int
    removed: dict[str, int] = field(default_factory=dict)


def _read(path: Path) -> Drawing:
    try:
        return ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        doc, auditor = recover.readfile(path)
        log.info("Recovered %s (%d fixes)", path, len(auditor.fixes))
        return doc
    except OSError as exc:
        raise LibraryError(f"Cannot read {path}: {exc}") from exc


def _to_dxf(src: Path, cadcraft: CadCraftService | None, workdir: Path) -> Path:
    if src.suffix.lower() == ".dxf":
        return src
    if src.suffix.lower() != ".dwg":
        raise LibraryError(f"Unsupported model format {src.suffix}; use DXF or DWG.")
    if cadcraft is None:
        raise LibraryError("DWG import needs CADCraft (cadcraft-cli) to convert to DXF.")
    return cadcraft.dwg_to_dxf(src, workdir / (src.stem + ".dxf"))


def import_model(
    src: Path,
    dest: Path,
    *,
    cadcraft: CadCraftService | None = None,
    scale: float | None = None,
    target_width_mm: float | None = None,
    keep_dimensions: bool = False,
    keep_texts: bool = True,
    keep_layers: list[str] | None = None,
) -> ImportReport:
    if not src.is_file():
        raise LibraryError(f"Model file not found: {src}")
    workdir = Path(tempfile.mkdtemp(prefix="cadelec-import-"))
    try:
        source = _read(_to_dxf(src, cadcraft, workdir))
        units = int(source.header.get("$INSUNITS", 0))
        removed: dict[str, int] = {}
        selected = []
        for entity in source.modelspace():
            kind = entity.dxftype()
            layer = entity.dxf.get("layer", "0")
            reason = None
            if kind in _DROP_TYPES:
                reason = kind
            elif _DROP_LAYER.search(layer):
                reason = "connection_points"
            elif not keep_dimensions and kind in _ANNOTATION_TYPES:
                reason = "dimensions"
            elif not keep_texts and kind in _TEXT_TYPES:
                reason = "texts"
            elif keep_layers and layer not in keep_layers:
                reason = "layer_filtered"
            if reason:
                removed[reason] = removed.get(reason, 0) + 1
            else:
                selected.append(entity)
        if not selected:
            raise LibraryError(f"Nothing left to import from {src} after cleaning.")

        target = ezdxf.new("R2018")
        target.header["$INSUNITS"] = _MM
        importer = Importer(source, target)
        importer.import_entities(selected, target.modelspace())
        importer.finalize()
        msp = target.modelspace()
        # attribute definitions inside imported blocks would print tag names
        for block in target.blocks:
            for attdef in [e for e in block if e.dxftype() == "ATTDEF"]:
                block.delete_entity(attdef)

        extents = bbox.extents(msp, fast=True)
        if not extents.has_data:
            raise LibraryError(f"{src} has no measurable geometry.")
        width, height = extents.size.x, extents.size.y
        if scale is None:
            if target_width_mm:
                scale = target_width_mm / width
            elif units == _INCH:
                scale = 25.4
            else:
                scale = 1.0
        matrix = Matrix44.translate(-extents.extmin.x, -extents.extmin.y, 0) @ Matrix44.scale(scale)
        for entity in list(msp):
            try:
                entity.transform(matrix)
            except (NotImplementedError, AttributeError, ValueError) as exc:
                msp.delete_entity(entity)
                removed["not_transformable"] = removed.get("not_transformable", 0) + 1
                log.debug("dropped %s: %s", entity.dxftype(), exc)
        dest.parent.mkdir(parents=True, exist_ok=True)
        target.saveas(dest)
        return ImportReport(
            dest, round(width * scale, 2), round(height * scale, 2), scale, units, len(msp), removed
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
