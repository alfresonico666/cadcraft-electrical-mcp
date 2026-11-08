# Funcionalidades

El servidor MCP **cadcraft-elec** tiene 41 herramientas, agrupadas por módulo. Cada herramienta
guarda el proyecto al instante en `<código>.elec.yaml`.

> Cada sección trae instrucciones de ejemplo que puedes escribirle a Claude tal cual.

## 1. Proyecto y normas (`server/tools/project_tools.py`)

| Herramienta | Qué hace |
|---|---|
| `project_create` | Crea un proyecto con los datos del cajetín y un perfil normativo. Los perfiles son `iec` (IEC 81346-2:2019, A3, rutas verticales), `iec_legacy` (-K/-F/-Q) y `nfpa` (escalera NFPA 79, ANSI B). Declara L1 L2 L3 N PE 24V 0V. |
| `project_open` / `project_list` / `project_info` | Abren, listan y resumen los proyectos del espacio de trabajo. |
| `project_update` | Cambia los datos del cajetín (autor, revisor, revisión, fecha...) o el perfil normativo. |
| `potential_set` | Declara potenciales extra (`L1_CTRL` ac_control, `24V_ACT` dc_plus...). El tipo define el color del conductor. |
| `standards_info` | Muestra los códigos de letra, colores, formato de hoja, alturas de texto, marcado de bornes y reglas de validación. |
| `symbols_list` | Muestra los símbolos disponibles (IEC 60617 / NFPA-JIC). |

> *"Crea el proyecto 26HA080 'Prensa de ensamble' con perfil NFPA, autor A. Castillo."*

## 2. Catálogo y dispositivos (`server/tools/device_tools.py`)

| Herramienta | Qué hace |
|---|---|
| `library_search` | Busca en el catálogo integrado (S7-1200, KTP400, Balluff BNI00HL/BNI007Z/BNI0067, Keyence DL-PN1/GT2/GL-T11R, SMC SY7320, gabinete NSYCRN54250P y genéricos) y en tus modelos importados. |
| `library_import_model` | Limpia un modelo 2D del fabricante (DXF o DWG) y lo registra en el catálogo como bloque 1:1 en mm. |
| `device_add` | Agrega uno o varios dispositivos, desde el catálogo (`catalog_id`) o por tipo (`kind`). La designación se asigna sola (-QA1, -KF2... o CR1, M1). |
| `device_update` | Edita datos. Renombrar actualiza todas las referencias. |
| `device_remove` / `device_list` | Eliminan (con `force` para limpiar referencias) y listan dispositivos. |

> *"Agrega 6 sensores inductivos de campo: Pieza presente, Empuje X atrás, Empuje Y atrás..."*
> *"Importa el DWG frontal de la HMI KTP400 de mi carpeta Modelos al catálogo."*

## 3. Esquemas, E/S, bornes y red (`server/tools/circuit_tools.py`)

| Herramienta | Qué hace |
|---|---|
| `sheet_add` | Crea hojas `power`, `control`, `plc_io`, `network`, `cover`, `terminal_plan` o `cabinet_layout`. |
| `sheet_add_paths` / `sheet_update` / `sheet_remove` / `sheet_move` / `sheet_get` | Editan hojas y circuitos. |
| `plc_io_assign` | Asigna canales DI/DO/AI/AQ. Las direcciones (`%I0.0`, `%Q0.0`, `%IW64`) y los bornes del módulo (`DIa.0`, `DQa.0`) salen solos. Verifica la cantidad de canales del catálogo. |
| `plc_io_remove` / `plc_io_list` | Quitan y listan asignaciones de E/S. |
| `terminals_add` | Crea borneras y bornes (numeración consecutiva o explícita; PE). |
| `terminals_assign_io` | Pasa cada dispositivo de campo por su propio borne: entradas `sensor → borne → PLC`, salidas `PLC → borne → carga`. |
| `terminals_list` / `terminals_remove` | Listan y quitan bornes. |
| `network_link` / `network_unlink` / `network_list` | Conectan puertos PROFINET, Ethernet o IO-Link, con cable y longitud. |

Cada circuito de una hoja de potencia o control se define así:

```json
{"label": "Bomba", "supply": ["L1","L2","L3"], "pe": true,
 "elements": [{"device": "-QB1"}, {"device": "-FC1"}, {"device": "-QA1"}, {"device": "-MA1"}]}
{"label": "Autorretención", "supply": ["24V"], "return_rail": "0V",
 "elements": [{"device": "-KF1", "symbol": "contact_no"}, {"device": "-QA1"}]}
```

Qué se resuelve solo al dibujar un circuito:
- **Símbolos**: salen del tipo de equipo (bobina, contacto de potencia, magnetotérmico, motor...).
- **Bornes**: se asignan según IEC 60947 (A1-A2; 13-14 y 23-24 en NA; 11-12 en NC; 95-96 en térmico; 1-2/3-4/5-6 en polos).
- **Referencias cruzadas**: contacto → `/hoja.columna` de la bobina, y bajo cada bobina el espejo de sus contactos.
- **Numeración de hilos**: los que tocan un riel llevan el nombre del potencial y los demás `<hoja><columna>-n`; en NFPA, el número de línea.
- **Color**: cada hilo toma el color de su clase de circuito (IEC 60204-1 / NFPA 79).
- **Paginación**: las hojas se paginan solas, y un circuito multipolar ocupa dos columnas.

> *"Agrega una hoja de control: paro de emergencia y rearme alimentan el relé de seguridad -KF6,
> el contacto NA de -KF6 alimenta la bobina de -KF7 y su contacto enciende el piloto -PF2."*
> *"Asigna las entradas del PLC: I0.0 pieza presente, I0.1 empuje X atrás... y pásalas por la bornera -XD3."*
> *"Conecta el PLC X1P1 al puerto P1 del switch, P2 a la HMI, P3 al maestro IO-Link y su Port0 al hub."*

## 4. Gabinete, validación y salidas (`server/tools/output_tools.py`)

| Herramienta | Qué hace |
|---|---|
| `cabinet_configure` | Define el gabinete (por catálogo o medidas), la placa, las canaletas, las holguras, los equipos de puerta y la reserva mínima. |
| `cabinet_rails` / `cabinet_place` | Fijan qué equipo va en cada riel, o colocan un equipo a mano (coordenadas de placa). |
| `cabinet_plan` | Calcula la platina sin dibujarla: posiciones, ocupación de rieles y advertencias. |
| `validate` | Revisa 11 reglas: designaciones únicas y con el código correcto; referencias; conflictos de E/S y de puertos; bornes duplicados; alturas de texto; ajuste de la platina, reserva y encimamientos; referencias cruzadas; potenciales no declarados; equipos sin usar. |
| `build` | Genera el DXF del juego, el PDF multipágina (CADCraft), el DWG opcional, la platina 1:1, el XLSX/CSV y los PNG. |
| `sheet_preview` | Devuelve la imagen de una hoja para que Claude (y tú) la revisen. |
| `reports` | Exporta solo las listas: BOM, cables, bornes, E/S y red. |
| `cadcraft_status` | Muestra la versión de CADCraft y si la app está conectada. |
| `cadcraft_open` | Abre el juego de planos o la platina en la app de escritorio. Si no está abierta, la lanza con el puerto de control. |
| `cadcraft_execute` | Ejecuta cualquier comando del motor de CADCraft en la app abierta. |

> *"Configura el gabinete Schneider NSYCRN54250P con canaletas de 25×40 y pon la HMI, el paro y el
> puerto de servicio en la puerta. Calcula la platina y dime cuánto espacio libre queda."*
> *"Valida el proyecto y corrige lo que encuentres. Luego construye y muéstrame la hoja 3."*

## 5. Fuera de MCP

- `cadcraft-elec-mcp doctor`: diagnóstico de la instalación (rutas, versión de CADCraft, configuración).
- `examples/build_26ha076.py`: el flujo completo programado en Python. Sirve de referencia y de prueba.
- `scripts/gen_standards_doc.py`: regenera [STANDARDS.md](STANDARDS.md) desde los perfiles.

## Limitaciones conocidas (v0.1)

- **Símbolos**: se dibujan en código; no se importan bibliotecas QElectroTech/EPLAN.
- **Hojas de PLC**: se dibuja la caja del módulo con sus canales. La alimentación del PLC se dibuja como circuito en la hoja de 24 VDC.
- **Platina**: el acomodo automático usa rieles horizontales; para casos especiales usa `cabinet_rails` o `cabinet_place`.
- **NFPA**: los circuitos trifásicos se dibujan en peldaños horizontales con varios polos.
- **Cajetín corporativo**: se puede usar un DXF propio con campos `{project_title}`, `{sheet}`... (ver [CONFIGURATION.md](CONFIGURATION.md)).
