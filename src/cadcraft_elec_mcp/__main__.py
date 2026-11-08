"""Entry point: ``cadcraft-elec-mcp`` (stdio MCP server) and a couple of maintenance commands."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .config import Settings, default_config_file
from .logging_setup import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cadcraft-elec-mcp", description=__doc__)
    parser.add_argument("--version", action="version", version=f"cadcraft-elec-mcp {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser("doctor", help="check configuration and CADCraft installation")
    args = parser.parse_args(argv)

    settings = Settings()
    configure_logging(settings.log_level, settings.log_dir)

    if args.command == "doctor":
        from .cadcraft import CadCraftService

        report = {
            "version": __version__,
            "config_file": str(default_config_file()),
            "config_file_exists": default_config_file().is_file(),
            "workspace": str(settings.workspace_dir),
            "models_dir": str(settings.models_dir),
            "cadcraft": CadCraftService(settings).status(),
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    from .server.app import create_server

    create_server(settings).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
