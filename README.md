# cadcraft-electrical-mcp

**Servidor MCP para generar planos eléctricos industriales con Claude y [CADCraft](https://github.com/storytold/cadcraft).**

Describe tu máquina en lenguaje natural ("PLC S7-1200, HMI KTP400, switch Balluff, 4 electroválvulas
SMC, gabinete Spacial 500×400...") y Claude produce el juego completo de planos:

- **Esquemas eléctricos**: portada con índice, potencia AC, control y distribución 24 VDC con
  referencias cruzadas y espejo de contactos, y hojas de E/S del PLC.
- **Layout de gabinete y platina**: a escala 1:1 en un DXF de fabricación (con perforaciones y
  cotas) y a escala reducida en el juego de planos. Usa tus modelos 2D reales del fabricante.
- **Red PROFINET / Ethernet / IO-Link**: topología con puertos y cables.
- **Plano de borneras**, **BOM**, **lista de cables**, **lista de E/S** y **lista de red** en XLSX/CSV.
- **Validación normativa**: designaciones, conflictos de E/S y de puertos, referencias cruzadas,
  espacio de reserva y encimamientos en la platina.

Todo cumple un perfil normativo configurable:
- **IEC**: IEC 81346, 60617, 61082-1 y 60204-1.
- **IEC legado**: códigos de una letra (-K/-F/-Q).
- **NFPA 79**: escalera horizontal JIC/ANSI.

Los planos se generan como DXF y CADCraft los publica en **PDF multipágina**, **PNG** y **DWG**, y los
puede abrir en vivo en la aplicación de escritorio.

> Las [funcionalidades](docs/FEATURES.md) traen ejemplos de instrucciones, la [arquitectura](docs/ARCHITECTURE.md)
> incluye una guía de "si falla X, revisa Y", y hay una página con las [normas](docs/STANDARDS.md) y la
> [configuración](docs/CONFIGURATION.md).

---

## Cómo funciona

```
Claude ──MCP (stdio)──> cadcraft-elec-mcp
                          │ proyecto .elec.yaml (fuente de verdad, versionable en git)
                          │ → generadores → DXF determinista (ezdxf)
                          └──> CADCraft: cadcraft-cli (PDF / PNG / DWG / DWG→DXF)
                                         cadcraft --control 7979 (abrir en la app viva)
```

- **CADCraft ya trae su propio MCP genérico** (`cadcraft-cli mcp`) con primitivas de dibujo.
- **Este servidor agrega la capa eléctrica** que CADCraft no tiene: dispositivos, potenciales,
  bornes, E/S, cables, símbolos IEC/NFPA, cajetín, normas y validación.
- **El dibujo se hace en Python (ezdxf) en lugar de comando por comando en CADCraft** (pre-alfa).
  Así el resultado es reproducible y probado, y CADCraft se usa para lo que hace mejor: renderizar,
  publicar y visualizar.

## Requisitos

- Windows 10/11.
- [CADCraft](https://github.com/storytold/cadcraft/releases) **0.18 o superior** (`cadcraft-0.18.0-windows-x64.msi`).
- Una de estas dos opciones:
  - el **ejecutable** `cadcraft-elec-mcp.exe` de la página de *Releases* (no requiere Python);
  - **Python 3.11 o superior** (con `uv` o `pipx`).

## Instalación para el equipo

### Opción A: script automático (recomendada)

```powershell
git clone https://github.com/alfresonico666/cadcraft-electrical-mcp
cd cadcraft-electrical-mcp
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

El script:
1. Crea un entorno en `%LOCALAPPDATA%\cadcraft-elec-mcp` e instala el paquete.
2. Registra el servidor en **Claude Code** (alcance de usuario) y en **Claude Desktop**.
3. Opcionalmente registra también el MCP nativo de CADCraft (`-WithCadcraftMcp`).

Al final ejecuta `doctor` para comprobar que todo responde.

### Opción B: manual

```powershell
# con uv
uv tool install git+https://github.com/alfresonico666/cadcraft-electrical-mcp
# o con pipx
pipx install git+https://github.com/alfresonico666/cadcraft-electrical-mcp

cadcraft-elec-mcp doctor            # verifica CADCraft y la configuración
claude mcp add --scope user cadcraft-elec -- cadcraft-elec-mcp
```

En Claude Desktop, agrega esto a `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{ "mcpServers": { "cadcraft-elec": { "command": "cadcraft-elec-mcp", "args": [] } } }
```

Con el `.exe` de *Releases*, usa la ruta completa del ejecutable como `command`.

## Uso rápido

En Claude Code o Claude Desktop:

> Crea el proyecto 26HA076 "Máquina LVDT" para un cliente automotriz con perfil IEC. Agrega un S7-1200 1214C DC/DC/DC,
> una HMI KTP400, una fuente de 24 VDC 10 A con su magnetotérmico, 4 electroválvulas SMC SY7320 en las
> salidas Q0.0–Q0.3 y 4 sensores inductivos en I0.0–I0.3 pasando por la bornera -XD3. Genera las hojas de
> potencia, 24 VDC, E/S y red, configura el gabinete NSYCRN54250P, valida y construye el PDF.
> Muéstrame la hoja de E/S.

Claude seguirá este flujo:
1. `project_create`
2. `library_search` y `device_add`
3. `sheet_add`
4. `plc_io_assign` y `terminals_assign_io`
5. `network_link`
6. `cabinet_configure`
7. `validate` y `build`
8. `sheet_preview`

Los archivos quedan en `Documentos\CadElec\<proyecto>\output\`:

| Archivo | Contenido |
|---|---|
| `<código> - Planos Electricos.dxf / .pdf / .dwg` | juego completo de hojas |
| `<código> - Platina Electrica.dxf` | platina 1:1 para taller (perforaciones, cotas) |
| `<código> - Listas.xlsx` + `csv/` | BOM, cables, bornes, E/S, red |
| `preview/hoja-NN.png` | vistas previas |

Para ver el resultado en CADCraft: *"ábrelo en CADCraft"* (herramienta `cadcraft_open`).

### Usar tus modelos 2D del fabricante

> Importa `C:\...\Modelos\Siemens - PLC\PLC_Terminales.dxf` como modelo del catálogo
> `siemens-6es7214-1ag40-0xb0`.

`library_import_model` hace lo siguiente:
- convierte DWG a DXF con CADCraft;
- quita ATTDEF de CADENAS, puntos de conexión y cotas;
- normaliza a mm con la esquina en 0,0;
- registra el modelo en tu catálogo.

Desde entonces, la platina dibuja el equipo real. Los modelos **no se suben al repositorio**
(licencias de los fabricantes).

## Ejemplo completo

[`examples/build_26ha076.py`](examples/build_26ha076.py) reproduce el proyecto 26HA076 completo (8 hojas):

```powershell
python examples\build_26ha076.py --workspace C:\temp\CadElec --models "C:\...\26HA076\Modelos"
```

## Desarrollo

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -e ".[dev]"
ruff check src tests; mypy; pytest            # las pruebas de integración se omiten si no hay CADCraft
pyinstaller packaging\cadcraft-elec-mcp.spec  # genera dist\cadcraft-elec-mcp.exe
```

Hay CI en GitHub Actions (Windows) con lint, tipos y pruebas. Al crear un tag `v*` se publica el `.exe` en *Releases*.

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `cadcraft_not_installed` | Instala CADCraft o define `cadcraft_cli` en `config.toml` ([configuración](docs/CONFIGURATION.md)). |
| `cadcraft_connection` al abrir en vivo | La app no tiene puerto de control. `cadcraft_open` la lanza sola; si no, abre `cadcraft --control 7979`. |
| `pip install` falla descargando `mcp` (`InvalidChunkLength`) | Proxy o red corporativa. Usa el `.exe` de *Releases* o `pip install https://files.pythonhosted.org/.../mcp-2.3.0-py3-none-any.whl`. |
| Un equipo sale como rectángulo en la platina | No tiene modelo. Impórtalo con `library_import_model` o da `width_mm`/`height_mm` reales. |
| `cabinet_fit` reporta equipos sin colocar | La placa es chica: más placa, canaletas más delgadas (`duct_width`) o menos equipos por riel. |

Los registros quedan en `Documentos\CadElec\logs\cadcraft-elec-mcp.log`.

## Licencia

Apache-2.0. CADCraft es © storytold, Apache-2.0/MIT. Este proyecto no incluye modelos CAD de terceros.
