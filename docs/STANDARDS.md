# Normas y perfiles

> Archivo generado con `python scripts/gen_standards_doc.py` a partir de
> `src/cadcraft_elec_mcp/standards/profiles/*.yaml`. Para cambiar una regla edita el YAML, no este archivo.

| Perfil | Título | Orientación | Numeración de hilos | Hoja |
|---|---|---|---|---|
| `iec` | IEC (81346-2:2019 · 60617 · 61082-1 · 60204-1) | vertical | potential | A3 420×297 mm |
| `iec_legacy` | IEC (códigos de una letra, estilo IEC 60750) | vertical | potential | A3 420×297 mm |
| `nfpa` | NFPA 79 (ladder JIC/ANSI) | horizontal | line_reference | ANSI B 431.8×279.4 mm |

## Códigos de designación por tipo de equipo

| Tipo (`kind`) | iec | iec_legacy | nfpa |
|---|---|---|---|
| `contactor` | `-QA` | `-K` | `M` |
| `relay` | `-KF` | `-K` | `CR` |
| `safety_relay` | `-KF` | `-K` | `SR` |
| `timer_relay` | `-KF` | `-K` | `TR` |
| `mcb` | `-FC` | `-F` | `CB` |
| `mpcb` | `-QA` | `-Q` | `MPCB` |
| `fuse` | `-FC` | `-F` | `FU` |
| `rcd` | `-FB` | `-F` | `GFCI` |
| `surge_protector` | `-FA` | `-F` | `SPD` |
| `main_switch` | `-QB` | `-Q` | `DISC` |
| `overload` | `-FC` | `-F` | `OL` |
| `psu` | `-TB` | `-G` | `PS` |
| `transformer` | `-TA` | `-T` | `T` |
| `plc_cpu` | `-KF` | `-A` | `PLC` |
| `plc_module` | `-KF` | `-A` | `PLC` |
| `hmi` | `-PF` | `-A` | `HMI` |
| `network_switch` | `-KF` | `-A` | `ENET` |
| `iolink_master` | `-KF` | `-A` | `IOL` |
| `iolink_hub` | `-KF` | `-A` | `IOL` |
| `fieldbus_coupler` | `-KF` | `-A` | `COM` |
| `sensor` | `-BG` | `-B` | `PRX` |
| `pressure_sensor` | `-BP` | `-B` | `PRS` |
| `measuring_sensor` | `-BG` | `-B` | `SEN` |
| `safety_sensor` | `-BG` | `-B` | `SLC` |
| `solenoid_valve` | `-MB` | `-Y` | `SOL` |
| `valve_manifold` | `-MB` | `-Y` | `SOL` |
| `motor` | `-MA` | `-M` | `MTR` |
| `vfd` | `-TA` | `-T` | `VFD` |
| `pushbutton` | `-SF` | `-S` | `PB` |
| `estop` | `-SF` | `-S` | `ES` |
| `selector` | `-SF` | `-S` | `SS` |
| `pilot_lamp` | `-PF` | `-H` | `LT` |
| `terminal_strip` | `-XD` | `-X` | `TB` |
| `connector` | `-XD` | `-X` | `CON` |
| `service_port` | `-XF` | `-X` | `CON` |
| `fan` | `-EC` | `-E` | `FAN` |
| `cable` | `-WD` | `-W` | `W` |
| `pc` | `-KF` | `-A` | `PC` |
| `generic` | `-A` | `-A` | `U` |

## Colores de conductores

| Clase de circuito | iec | iec_legacy | nfpa |
|---|---|---|---|
| `ac_phase` | BK – Negro (potencia AC/DC) (2.5 mm²) | BK – Negro (potencia AC/DC) (2.5 mm²) | BLK – Black (power) (2.08 mm²) |
| `ac_neutral` | BU – Azul claro (neutro) (2.5 mm²) | BU – Azul claro (neutro) (2.5 mm²) | WHT – White (grounded conductor) (2.08 mm²) |
| `pe` | GNYE – Verde-amarillo (PE) (2.5 mm²) | GNYE – Verde-amarillo (PE) (2.5 mm²) | GRN – Green (equipment grounding) (2.08 mm²) |
| `ac_control` | RD – Rojo (control AC) (1 mm²) | RD – Rojo (control AC) (1 mm²) | RED – Red (AC control) (0.82 mm²) |
| `dc_plus` | DBU – Azul oscuro (control DC) (0.75 mm²) | DBU – Azul oscuro (control DC) (0.75 mm²) | BLU – Blue (DC control) (0.82 mm²) |
| `dc_minus` | DBU – Azul oscuro (control DC) (0.75 mm²) | DBU – Azul oscuro (control DC) (0.75 mm²) | WHT/BLU – White w/ blue stripe (grounded DC) (0.82 mm²) |
| `external` | OG – Naranja (alimentación externa) (1 mm²) | OG – Naranja (alimentación externa) (1 mm²) | ORG – Orange/Yellow (externally fed) (0.82 mm²) |

## Alturas de texto (mm, ISO 3098)

| Uso | IEC | NFPA |
|---|---|---|
| general | 2.5 | 2.5 |
| terminal | 2.5 | 2.5 |
| wire_number | 2.5 | 2.5 |
| designation | 3.5 | 3.5 |
| heading | 5 | 5 |
| title | 7 | 7 |
| minimum | 2.5 | 2.5 |

## Marcado de bornes (IEC 60947 / IEC 60445)

- **coil**: `['A1', 'A2']`
- **power_poles**: `[['1', '2'], ['3', '4'], ['5', '6'], ['7', '8']]`
- **aux_no**: `['x3', 'x4']`
- **aux_nc**: `['x1', 'x2']`
- **overload_nc**: `['95', '96']`
- **overload_no**: `['97', '98']`
- **motor**: `['U1', 'V1', 'W1']`
- **dc_supply**: `['L+', 'M']`

## Referencias normativas aplicadas

- **IEC 81346-1/-2:2019** – designación de referencia `=función +ubicación -producto :borne`.
- **IEC 60617** – símbolos gráficos (perfil `iec`); **IEEE 315 / NFPA 79 Anexo** (perfil `nfpa`).
- **IEC 61082-1** – hojas con rejilla de columnas y referencias cruzadas `/hoja.columna` y espejo de
  contactos bajo cada bobina.
- **IEC 60204-1 §13.2.4 / NFPA 79 §13.2** – colores de conductores.
- **IEC 60947 / IEC 60445** – marcado de bornes (A1-A2, 13-14, 21-22, 95-96, U1-V1-W1, L+/M).
- **ISO 5457 / ISO 7200 / ISO 3098 / ISO 128** – formato de hoja, cajetín, textos y grosores.
- **EN 60715** – riel DIN TS35; buenas prácticas de gabinete (reserva ≥ 20 %, separación a canaleta).

Los códigos de dos letras de IEC 81346-2:2019 siguen la práctica habitual de EPLAN/VDMA; verifica
contra la edición vigente de la norma si tu cliente lo exige. El perfil `iec_legacy` usa las letras
simples (-K, -F, -Q, -S, -H, -X) que siguen siendo comunes en QElectroTech.
