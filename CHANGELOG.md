# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [0.1.0] - 2026-11-08

### Agregado
- Servidor MCP (stdio, SDK `mcp` 2.x) con 41 herramientas de dominio eléctrico.
- Perfiles normativos en datos: `iec` (IEC 81346-2:2019), `iec_legacy` (-K/-F/-Q) y `nfpa` (NFPA 79).
- Biblioteca de símbolos IEC 60617 y NFPA/JIC con atributos, y asignación de bornes IEC 60947.
- Motor de rutas de corriente:
  - orientación vertical (IEC) u horizontal (NFPA);
  - referencias cruzadas y espejo de contactos;
  - numeración y colores de hilos;
  - paginación automática.
- Hojas: portada con índice, potencia, control, E/S de PLC, red PROFINET/IO-Link, plano de borneras y
  layout de gabinete (escala normalizada).
- Platina 1:1 para fabricación: canaletas, rieles TS35, perforaciones, cotas y vista de puerta.
- Importador de modelos 2D del fabricante (DXF/DWG vía CADCraft): limpieza CADENAS y normalización a mm.
- Catálogo integrado (Siemens S7-1200/KTP400, Balluff, Keyence, SMC, Schneider, genéricos) y catálogos
  de usuario.
- Reportes BOM, cables, bornes, E/S y red en XLSX/CSV.
- Validador con 11 reglas.
- Integración con CADCraft 0.18:
  - PDF multipágina (`pdfbook` / `plot`), PNG y DWG;
  - apertura en la app vía puerto de control con token.
- Empaquetado: `pip`/`uv`/`pipx`, `.exe` con PyInstaller, `scripts/install.ps1` y CI en GitHub Actions.
