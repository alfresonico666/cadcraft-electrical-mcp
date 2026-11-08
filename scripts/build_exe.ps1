<#
.SYNOPSIS
  Genera dist\cadcraft-elec-mcp.exe (un solo archivo, no requiere Python en la PC destino).
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    python -m pip install --quiet -e ".[dev]"
    pyinstaller packaging\cadcraft-elec-mcp.spec --noconfirm --distpath dist --workpath build
    & dist\cadcraft-elec-mcp.exe --version
} finally {
    Pop-Location
}
