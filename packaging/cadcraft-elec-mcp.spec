# PyInstaller spec: single-file console exe of the MCP server (stdio).
# Build:  pyinstaller packaging/cadcraft-elec-mcp.spec --noconfirm
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
datas += collect_data_files("cadcraft_elec_mcp")          # standards profiles + built-in catalog (YAML)
datas += collect_data_files("ezdxf")                       # fonts, resources
hiddenimports = (
    collect_submodules("cadcraft_elec_mcp")
    + collect_submodules("mcp", filter=lambda name: not name.startswith("mcp.cli"))  # cli needs typer
    + collect_submodules("mcp_types")
)

a = Analysis(
    ["launcher.py"],
    pathex=["../src"],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "PySide6", "PyQt5", "tkinter", "numpy.f2py"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="cadcraft-elec-mcp",
    console=True,      # stdio transport needs a console subsystem
    upx=False,         # UPX triggers antivirus false positives
)
