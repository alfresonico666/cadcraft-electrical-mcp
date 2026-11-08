"""Regenerate docs/STANDARDS.md from the YAML profiles (keeps docs and code in sync).

    python scripts/gen_standards_doc.py
"""

from __future__ import annotations

from pathlib import Path

from cadcraft_elec_mcp.domain.model import DeviceKind, PotentialKind
from cadcraft_elec_mcp.standards import load_profile

PROFILES = ["iec", "iec_legacy", "nfpa"]
OUT = Path(__file__).resolve().parents[1] / "docs" / "STANDARDS.md"


def main() -> None:
    profiles = [load_profile(p) for p in PROFILES]
    lines = [
        "# Normas y perfiles",
        "",
        "> Archivo generado con `python scripts/gen_standards_doc.py` a partir de",
        "> `src/cadcraft_elec_mcp/standards/profiles/*.yaml`. Para cambiar una regla edita el YAML, no este archivo.",
        "",
        "| Perfil | Título | Orientación | Numeración de hilos | Hoja |",
        "|---|---|---|---|---|",
    ]
    for p in profiles:
        lines.append(f"| `{p.name}` | {p.title} | {p.orientation} | {p.numbering.value} | "
                     f"{p.sheet.paper} {p.sheet.width:g}×{p.sheet.height:g} mm |")
    lines += ["", "## Códigos de designación por tipo de equipo", "",
              "| Tipo (`kind`) | " + " | ".join(p.name for p in profiles) + " |",
              "|---|" + "---|" * len(profiles)]
    for kind in DeviceKind:
        lines.append(f"| `{kind.value}` | " + " | ".join(f"`{p.tag_prefix(kind)}`" for p in profiles) + " |")
    lines += ["", "## Colores de conductores", "",
              "| Clase de circuito | " + " | ".join(p.name for p in profiles) + " |",
              "|---|" + "---|" * len(profiles)]
    for kind in PotentialKind:
        cells = [f"{p.wire_color(kind).code} – {p.wire_color(kind).name} ({p.cross_sections_mm2[kind]:g} mm²)"
                 for p in profiles]
        lines.append(f"| `{kind.value}` | " + " | ".join(cells) + " |")
    iec = profiles[0]
    lines += ["", "## Alturas de texto (mm, ISO 3098)", "", "| Uso | IEC | NFPA |", "|---|---|---|"]
    for name in ("general", "terminal", "wire_number", "designation", "heading", "title", "minimum"):
        lines.append(f"| {name} | {getattr(iec.text, name):g} | {getattr(profiles[2].text, name):g} |")
    lines += ["", "## Marcado de bornes (IEC 60947 / IEC 60445)", ""]
    for key, value in iec.terminal_marking.items():
        lines.append(f"- **{key}**: `{value}`")
    lines += [
        "", "## Referencias normativas aplicadas", "",
        "- **IEC 81346-1/-2:2019** – designación de referencia `=función +ubicación -producto :borne`.",
        "- **IEC 60617** – símbolos gráficos (perfil `iec`); **IEEE 315 / NFPA 79 Anexo** (perfil `nfpa`).",
        "- **IEC 61082-1** – hojas con rejilla de columnas y referencias cruzadas `/hoja.columna` y espejo de",
        "  contactos bajo cada bobina.",
        "- **IEC 60204-1 §13.2.4 / NFPA 79 §13.2** – colores de conductores.",
        "- **IEC 60947 / IEC 60445** – marcado de bornes (A1-A2, 13-14, 21-22, 95-96, U1-V1-W1, L+/M).",
        "- **ISO 5457 / ISO 7200 / ISO 3098 / ISO 128** – formato de hoja, cajetín, textos y grosores.",
        "- **EN 60715** – riel DIN TS35; buenas prácticas de gabinete (reserva ≥ 20 %, separación a canaleta).",
        "",
        "Los códigos de dos letras de IEC 81346-2:2019 siguen la práctica habitual de EPLAN/VDMA; verifica",
        "contra la edición vigente de la norma si tu cliente lo exige. El perfil `iec_legacy` usa las letras",
        "simples (-K, -F, -Q, -S, -H, -X) que siguen siendo comunes en QElectroTech.",
        "",
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
