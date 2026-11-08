"""Write report tables to XLSX (one sheet per table) and CSV (one file per table)."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .lists import Table

_HEADER_FILL = PatternFill("solid", fgColor="1F3864")
_HEADER_FONT = Font(bold=True, color="FFFFFF")


def to_xlsx(tables: list[Table], path: Path, title: str = "") -> Path:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for table in tables:
        sheet = workbook.create_sheet(table.name[:31])
        sheet.append(table.columns)
        for cell in sheet[1]:
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in table.rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        if table.rows:
            sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(table.columns, start=1):
            values = [str(column), *(str(r[index - 1]) for r in table.rows if index - 1 < len(r))]
            sheet.column_dimensions[get_column_letter(index)].width = min(max(len(v) for v in values) + 2, 60)
    if title:
        workbook.properties.title = title
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def to_csv(tables: list[Table], directory: Path, prefix: str) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table in tables:
        file = directory / f"{prefix} - {table.name}.csv"
        with file.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=",")
            writer.writerow(table.columns)
            writer.writerows(table.rows)
        written.append(file)
    return written
