# Arquitectura

```
src/cadcraft_elec_mcp/
├── __main__.py          CLI: `cadcraft-elec-mcp [serve|doctor]`
├── errors.py            jerarquía de excepciones con código estable (project, cadcraft, layout...)
├── logging_setup.py     log a stderr + archivo rotativo (stdout = canal MCP)
├── config/              Settings (env CADELEC_* > config.toml > defaults)
├── domain/              MODELO PURO: Project, Device, CircuitPath, PlcIoChannel, NetworkLink,
│                        TerminalStrip, CabinetSpec · designaciones IEC 81346 · numeración de hilos
├── standards/           perfiles normativos en YAML (iec, iec_legacy, nfpa) + cargador con herencia
├── symbols/             símbolos IEC 60617 / NFPA dibujados en código → bloques DXF con atributos;
│                        símbolo por defecto por tipo de equipo; asignación de bornes IEC 60947
├── drawing/             documento DXF (capas/estilos del perfil), marco ISO 5457, cajetín
├── generators/          un generador por tipo de hoja:
│   ├── ladder.py           motor de rutas de corriente (vertical IEC / horizontal NFPA)
│   ├── schematic.py        hojas de potencia y control
│   ├── plc_io.py           hojas de E/S del PLC
│   ├── network.py          topología PROFINET / IO-Link
│   ├── terminal_plan.py    plano de borneras
│   ├── cabinet_layout.py   platina + puerta (DXF)
│   ├── cover.py            portada + índice
│   └── crossref.py         referencias cruzadas y espejo de contactos
├── layout/              planificador de platina (geometría pura: rieles, canaletas, ajuste, reserva)
├── library/             catálogo de dispositivos (YAML) + importador de modelos del fabricante
├── reports/             BOM, cables, bornes, E/S, red → XLSX / CSV
├── validation/          reglas independientes (patrón rule object) + motor
├── persistence/         proyecto ⇄ YAML (escritura atómica)
├── cadcraft/            ÚNICO punto de contacto con CADCraft: descubrimiento, CLI, puerto de control
├── application/         casos de uso (sesión, proyectos, dispositivos, hojas, E/S, red, gabinete, build)
└── server/              capa MCP delgada: herramientas por grupo, anotaciones, traducción de errores
```

**Dirección de las dependencias:**
`server → application → (generators, layout, reports, validation, library, persistence, cadcraft) → (drawing, symbols, standards) → domain`

`domain` no importa nada del proyecto. `cadcraft` es el único módulo que lanza procesos o abre sockets.

## Flujo de `build`

1. `application.build.compile_project` crea un DXF nuevo con las capas del perfil y genera las hojas
   en dos pasadas:
   - **Pasada 1**: portada, potencia, control, E/S y red. Estas hojas construyen la lista de
     conexiones (`ctx.wires`) y las referencias cruzadas.
   - **Pasada 2**: plano de borneras y gabinete. Estas hojas consumen la lista de conexiones y el
     plan de la platina.
2. Se escriben las referencias cruzadas, se completa el índice de la portada y se insertan los
   cajetines (que necesitan el total de hojas).
3. Se guardan el DXF y la platina 1:1.
4. `cadcraft.CadCraftService`:
   - genera el PDF con `pdfbook` (papeles ISO A) o con `plot` y unión con pypdf (ANSI B);
   - genera los PNG con `plot` y el DWG con `convert`.
5. Se generan los reportes XLSX/CSV y se ejecuta la validación.

Todas las hojas viven en el *model space*, en una fila. Cada hoja tiene un marco del tamaño exacto
del papel, que es lo que `pdfbook` usa para paginar.

## Si falla X, revisa Y

| Síntoma | Módulo |
|---|---|
| Error `[cadcraft_*]`, no se genera el PDF/PNG/DWG | `cadcraft/cli.py`, `cadcraft/service.py` (ejecuta `cadcraft-elec-mcp doctor`) |
| No abre en la app / `unauthorized` | `cadcraft/control.py` (token en `%LOCALAPPDATA%\cadcraft-control-<puerto>.token`) |
| Un símbolo se ve mal | `symbols/iec.py` o `symbols/nfpa.py` (función del símbolo) |
| Bornes 13-14 / A1-A2 incorrectos | `symbols/registry.py` (`TerminalAllocator`) |
| Elementos encimados o columnas desbordadas | `generators/ladder.py` (constantes `ELEMENT_GAP`, `POLE_PITCH`, `slots_needed`) |
| Referencias `/hoja.columna` o espejo de contactos | `generators/crossref.py` |
| Números o colores de hilo | `domain/numbering.py`, `standards/profiles/*.yaml` (`wire_colors`) |
| Código de letra (-KF, CR...) | `standards/profiles/*.yaml` (`tag.codes`) |
| Hoja de E/S (caja PLC, direcciones) | `generators/plc_io.py`, `application/io_terminals.py` |
| Red mal dibujada | `generators/network.py` |
| Platina: equipo fuera de lugar o sin colocar | `layout/cabinet_planner.py` (posiciones), `application/cabinet.py` (tamaños) |
| Platina: dibujo, cotas o modelo | `generators/cabinet_layout.py`, `library/importer.py` |
| Cajetín | `drawing/title_block.py` |
| Error de validación inesperado | `validation/rules.py` (cada regla es una clase) |
| El proyecto no carga | `persistence/store.py` (mensaje con el campo inválido del YAML) |
| La herramienta MCP no aparece o sus parámetros están mal | `server/tools/*.py` |

## Decisiones

- **El YAML es la fuente de verdad.** Regenerar es idempotente y los cambios son revisables en git.
- **Pocas herramientas de dominio, no primitivas de dibujo.** La IA describe la instalación eléctrica,
  no líneas; el MCP nativo de CADCraft sigue disponible para retoques.
- **Las normas son datos.** Agregar una norma (por ejemplo JIS) = crear un YAML con `extends: iec`.
- **No se distribuyen modelos ni plantillas de terceros.** Los catálogos de usuario apuntan a rutas locales.
