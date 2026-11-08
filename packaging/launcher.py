"""PyInstaller entry point (absolute import; __main__.py uses package-relative imports)."""

from cadcraft_elec_mcp.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
