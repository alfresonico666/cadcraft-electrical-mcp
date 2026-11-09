# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [0.2.0] - 2026-11-09

### Agregado
- Supresor de picos (`surge_protector`, símbolo `surge`, código -FA) e interruptor diferencial (símbolo `rcd`).
- `CircuitPath.feeds`: flechas de continuación de potencial (la acometida alimenta L1/N1, un fusible
  alimenta 24V_KEYENCE...). Los rieles muestran tensión y origen ("desde -FC1:2").
- `library_import_model` conserva E/S, puertos y bornes de la entrada de catálogo existente.
- Catálogo: Mean Well HDR-30/60-24, Siemens 5SL4101-6, SPD, RCD, seccionador y portafusibles 1P+N.
- Planificador de platina: reparte respetando la reserva objetivo por riel cuando cabe en altura.

### Mejorado
- Números de hilo solo cuando caben en el tramo; PE debajo de equipos tipo caja.
- Designaciones dentro de cada equipo DIN en la platina; textos de cajetín que se ajustan a su celda.
- Hoja de red con etiquetas en dos renglones y leyenda de colores.

## [0.1.1] - 2026-11-08

### Corregido
- Hoja de red: puerto y cable en una línea sobre cada equipo (antes se encimaban), descripciones en dos líneas.
- Instalador compatible con Windows PowerShell 5.1 (errores de stderr nativo, acentos con BOM).

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
