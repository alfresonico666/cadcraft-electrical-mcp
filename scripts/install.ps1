<#
.SYNOPSIS
  Instala cadcraft-elec-mcp para el usuario actual y lo registra en Claude Code y Claude Desktop.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -WithCadcraftMcp
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Exe C:\Tools\cadcraft-elec-mcp.exe   # sin Python
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "cadcraft-elec-mcp"),
    [string]$Exe = "",                # usar un .exe de Releases en lugar de instalar con Python
    [switch]$WithCadcraftMcp,         # registrar también el MCP nativo de CADCraft
    [int]$ControlPort = 7979,
    [switch]$SkipClaudeCode,
    [switch]$SkipClaudeDesktop
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$mcpWheel = "https://files.pythonhosted.org/packages/20/d7/4a2878f128df729db3ca04e71bfce26405cc2e0c9ebe19c592feeb4c61b9/mcp-2.3.0-py3-none-any.whl"

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }

# Windows PowerShell 5.1 turns any stderr line of a native program into a terminating error when
# ErrorActionPreference is Stop; run native tools through this helper and check the exit code instead.
function Invoke-Native {
    param([string]$FilePath, [string[]]$Arguments, [switch]$AllowFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host "    $_" }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0 -and -not $AllowFailure) { throw "$FilePath $($Arguments -join ' ') failed ($code)" }
    return $code
}

# --- 1. Servidor ------------------------------------------------------------------------------------
if ($Exe) {
    if (-not (Test-Path $Exe)) { throw "No existe $Exe" }
    $serverExe = (Resolve-Path $Exe).Path
} else {
    Write-Step "Instalando con Python en $InstallDir"
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "Python 3.11+ no encontrado. Instálalo o usa -Exe con el ejecutable de Releases." }
    $ok = Invoke-Native python @("-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)") -AllowFailure
    if ($ok -ne 0) { throw "Se requiere Python 3.11 o superior." }
    $venv = Join-Path $InstallDir "venv"
    if (-not (Test-Path $venv)) { Invoke-Native python @("-m", "venv", $venv) | Out-Null }
    $venvPython = Join-Path $venv "Scripts\python.exe"
    Invoke-Native $venvPython @("-m", "pip", "install", "--quiet", "--upgrade", "pip") -AllowFailure | Out-Null
    $code = Invoke-Native $venvPython @("-m", "pip", "install", "--quiet", $repo) -AllowFailure
    if ($code -ne 0) {
        Write-Warning "pip falló (algunas redes corrompen el índice de 'mcp'); instalando la rueda directa."
        Invoke-Native $venvPython @("-m", "pip", "install", "--quiet", $mcpWheel) | Out-Null
        Invoke-Native $venvPython @("-m", "pip", "install", "--quiet", $repo) | Out-Null
    }
    $serverExe = Join-Path $venv "Scripts\cadcraft-elec-mcp.exe"
}

Write-Step "Diagnóstico"
Invoke-Native $serverExe @("doctor") | Out-Null

# --- 2. CADCraft ------------------------------------------------------------------------------------
$cadcraftCli = $null
foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "CADCraft\cadcraft-cli.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\ArtCraft\CADCraft\cadcraft-cli.exe"))) {
    if (Test-Path $candidate) { $cadcraftCli = $candidate; break }
}
if (-not $cadcraftCli) { Write-Warning "CADCraft no encontrado: instálalo desde https://github.com/storytold/cadcraft/releases" }

# --- 3. Claude Code -------------------------------------------------------------------------------------
if (-not $SkipClaudeCode) {
    if (Get-Command claude -ErrorAction SilentlyContinue) {
        Write-Step "Registrando en Claude Code (scope user)"
        Invoke-Native claude @("mcp", "remove", "--scope", "user", "cadcraft-elec") -AllowFailure | Out-Null
        Invoke-Native claude @("mcp", "add", "--scope", "user", "cadcraft-elec", "--", $serverExe) | Out-Null
        if ($WithCadcraftMcp -and $cadcraftCli) {
            Invoke-Native claude @("mcp", "remove", "--scope", "user", "cadcraft") -AllowFailure | Out-Null
            Invoke-Native claude @("mcp", "add", "--scope", "user", "cadcraft", "--", $cadcraftCli, "mcp",
                "--connect", "127.0.0.1:$ControlPort", "--lazy") | Out-Null
        }
    } else {
        Write-Warning "No se encontró 'claude' (Claude Code); omitiendo ese registro."
    }
}

# --- 4. Claude Desktop ------------------------------------------------------------------------------------
if (-not $SkipClaudeDesktop) {
    $configPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
    Write-Step "Registrando en Claude Desktop ($configPath)"
    New-Item -ItemType Directory -Force -Path (Split-Path $configPath) | Out-Null
    $config = if (Test-Path $configPath) { Get-Content $configPath -Raw | ConvertFrom-Json } else { New-Object psobject }
    if (-not $config.PSObject.Properties["mcpServers"]) {
        $config | Add-Member -NotePropertyName mcpServers -NotePropertyValue (New-Object psobject)
    }
    $entry = [pscustomobject]@{ command = $serverExe; args = @() }
    $config.mcpServers | Add-Member -NotePropertyName "cadcraft-elec" -NotePropertyValue $entry -Force
    if ($WithCadcraftMcp -and $cadcraftCli) {
        $native = [pscustomobject]@{ command = $cadcraftCli; args = @("mcp", "--connect", "127.0.0.1:$ControlPort", "--lazy") }
        $config.mcpServers | Add-Member -NotePropertyName "cadcraft" -NotePropertyValue $native -Force
    }
    if (Test-Path $configPath) { Copy-Item $configPath "$configPath.bak" -Force }
    $json = $config | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Reinicia Claude Desktop para cargar el servidor."
}

Write-Step "Listo. Servidor: $serverExe"
