# Configuración

Orden de prioridad:
1. Variables de entorno `CADELEC_*`.
2. `%APPDATA%\cadcraft-elec-mcp\config.toml` (o la ruta indicada en `CADELEC_CONFIG`).
3. Valores por defecto.

| Clave (`config.toml`) | Variable de entorno | Por defecto | Uso |
|---|---|---|---|
| `cadcraft_cli` | `CADELEC_CADCRAFT_CLI` | se busca sola (registro, `Program Files`, PATH) | ruta de `cadcraft-cli.exe` |
| `cadcraft_app` | `CADELEC_CADCRAFT_APP` | junto a `cadcraft-cli.exe` | ruta de `cadcraft.exe` |
| `control_port` | `CADELEC_CONTROL_PORT` | `7979` | puerto de control de la app de escritorio |
| `cli_timeout_s` | `CADELEC_CLI_TIMEOUT_S` | `180` | límite de tiempo por llamada a la CLI |
| `workspace_dir` | `CADELEC_WORKSPACE_DIR` | `~\Documents\CadElec` | proyectos y salidas |
| `library_catalogs` | — | `[]` | catálogos YAML adicionales (por ejemplo, el catálogo común del equipo) |
| `library_models_dir` | `CADELEC_LIBRARY_MODELS_DIR` | `<workspace>\library` | modelos limpios y `catalog.yaml` de usuario |
| `title_block_template` | `CADELEC_TITLE_BLOCK_TEMPLATE` | — | DXF de cajetín corporativo |
| `default_profile` | `CADELEC_DEFAULT_PROFILE` | `iec` | perfil al crear proyectos |
| `font` | `CADELEC_FONT` | `arial.ttf` | fuente TrueType de los textos |
| `log_level` | `CADELEC_LOG_LEVEL` | `INFO` | `DEBUG` para diagnosticar |

Ejemplo completo: [`examples/config.example.toml`](../examples/config.example.toml).

## Catálogo del equipo

Para compartir un catálogo, ponlo en una carpeta de red o en un repositorio y agrégalo en
`library_catalogs`. Formato:

```yaml
devices:
  - id: smc-ss5y7-20-07
    manufacturer: SMC
    part_number: SS5Y7-20-07
    description: "Manifold SY7000 7 estaciones"
    kind: valve_manifold        # ver standards_info → codes
    mount: din_rail             # din_rail | backplate | door | field
    width_mm: 150
    height_mm: 120
    ports: []
    model_dxf: "\\\\servidor\\cad\\modelos\\SS5Y7-20-07.dxf"   # rutas relativas = relativas al YAML
    io: {}                      # PLC / módulos: {DI: 16, DO: 16}
    io_terminals: {}            # {DI: [DI0, DI1, ...]}
```

## Cajetín corporativo

1. Dibuja tu cajetín en un DXF propio, solo el cajetín, en mm.
2. En los textos que deban rellenarse escribe el campo entre llaves:
   - `{company}`, `{client}`, `{plant}`;
   - `{project_title}`, `{project_code}`, `{machine}`;
   - `{sheet_title}`, `{sheet}`;
   - `{author}`, `{reviewer}`, `{date}`, `{revision}`;
   - `{standard}`, `{file}`, `{description}`.
3. Configura `title_block_template = "C:/ruta/cajetin.dxf"`.

El dibujo se escala para ocupar el área del cajetín (franja inferior de la hoja) y cada campo se
convierte en un atributo.
