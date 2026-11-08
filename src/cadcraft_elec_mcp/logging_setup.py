"""Logging configuration.

stdout is the MCP transport, so logs must NEVER go there: they go to stderr and to a rotating file
inside the workspace (``<workspace>/logs/cadcraft-elec-mcp.log``).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "cadcraft_elec_mcp"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(stderr_handler)

    # third-party libraries are chatty at INFO (ezdxf reports every dictionary it creates)
    for noisy in ("ezdxf", "fontTools", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "cadcraft-elec-mcp.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter(_FORMAT))
            logger.addHandler(file_handler)
        except OSError as exc:  # pragma: no cover - depends on the file system
            logger.warning("File logging disabled: %s", exc)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Child logger of the package logger (``cadcraft_elec_mcp.<name>``)."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
