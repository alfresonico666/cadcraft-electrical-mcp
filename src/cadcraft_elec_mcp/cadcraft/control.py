"""Client for the CADCraft desktop *control port* (``cadcraft --control PORT``).

Protocol (CADCraft ``docs/control-protocol.md``): one JSON object per line over loopback TCP, each
request carries the session token stored in ``%LOCALAPPDATA%/cadcraft-control-<port>.token``.
Replies are ``{"id", "ok", "result" | "error", "state"?}``. Only read-only methods are retried.
"""

from __future__ import annotations

import itertools
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from ..errors import CadCraftCommandError, CadCraftConnectionError
from ..logging_setup import get_logger

log = get_logger("cadcraft.control")

READ_ONLY_METHODS = frozenset(
    {
        "drawing.inspect",
        "engine.commands",
        "cmdline.state",
        "control.methods",
        "ping",
        "ui.inspect",
        "ui.render",
        "ui.screenshot",
    }
)


def token_path(port: int) -> Path:
    name = f"cadcraft-control-{port}.token"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise CadCraftConnectionError("LOCALAPPDATA is not set; cannot locate the control token.")
        return Path(base) / name
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return Path(runtime) / name if runtime else Path.home() / ".cache" / name


class ControlClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 7979, timeout_s: float = 90.0) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self._ids = itertools.count(1)

    def _read_token(self) -> str:
        path = token_path(self.port)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CadCraftConnectionError(
                f"CADCraft control token not found ({path}).",
                hint=f"Start the desktop app with: cadcraft --control {self.port}",
            ) from exc

    def is_available(self) -> bool:
        try:
            return bool(self.request("ping") == "pong")
        except (CadCraftConnectionError, CadCraftCommandError):
            return False

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        attempts = 2 if method in READ_ONLY_METHODS else 1
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                return self._request_once(method, params or {})
            except CadCraftConnectionError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def _request_once(self, method: str, params: dict[str, Any]) -> Any:
        request_id = next(self._ids)
        payload = {"id": request_id, "method": method, "params": params, "token": self._read_token()}
        try:
            with socket.create_connection((self.host, self.port), timeout=0.8) as sock:
                sock.settimeout(self.timeout_s)
                sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                reply = self._read_line(sock)
        except OSError as exc:
            raise CadCraftConnectionError(
                f"Cannot reach CADCraft at {self.host}:{self.port}: {exc}",
                hint=f"Start the desktop app with: cadcraft --control {self.port}",
            ) from exc
        if not reply.get("ok", False):
            state = reply.get("state", "unknown")
            raise CadCraftCommandError(f"{method} failed ({state}): {reply.get('error')}")
        return reply.get("result")

    @staticmethod
    def _read_line(sock: socket.socket) -> dict[str, Any]:
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b"\n"):
                break
        raw = b"".join(chunks).decode("utf-8").strip()
        if not raw:
            raise CadCraftConnectionError("CADCraft closed the control connection without a reply.")
        data = json.loads(raw.splitlines()[0])
        if not isinstance(data, dict):
            raise CadCraftCommandError(f"Unexpected control reply: {raw[:200]}")
        return data

    # -- convenience wrappers -------------------------------------------------------------------------
    def open(self, path: Path) -> Any:
        return self.request("app.open", {"path": str(path)})

    def execute(self, command: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("engine.execute", {"command": command, "params": params or {}})

    def render(self, width: int = 1600, height: int = 1000, window: list[list[float]] | None = None) -> Any:
        params: dict[str, Any] = {"width": width, "height": height, "fit": window is None}
        if window is not None:
            params["window"] = window
        return self.request("ui.render", params)

    def script(self, text: str) -> Any:
        return self.request("cmdline.script", {"text": text})
