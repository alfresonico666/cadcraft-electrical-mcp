"""Uniform error translation for MCP tools: domain errors become readable ``ToolError`` s."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from ..errors import CadElecError
from ..logging_setup import get_logger

log = get_logger("server")

F = TypeVar("F", bound=Callable[..., Any])


def tool_errors(fn: F) -> F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except CadElecError as exc:
            log.info("%s -> %s", fn.__name__, exc)
            raise ToolError(str(exc)) from exc
        except ValidationError as exc:
            log.info("%s -> validation: %s", fn.__name__, exc)
            raise ToolError(f"[invalid_input] {exc}") from exc
        except Exception as exc:  # unexpected: keep the server alive, log the trace
            log.exception("Unexpected error in %s", fn.__name__)
            raise ToolError(f"[internal] {type(exc).__name__}: {exc}") from exc

    return wrapper  # type: ignore[return-value]
