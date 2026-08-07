"""Define stable application errors shared by Ask interface adapters."""

from __future__ import annotations


class GroundedQueryError(RuntimeError):
    """Carry a stable application error across HTTP and MCP transports."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        """Record the public error code, safe message, and transport status."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def raise_grounded_error(code: str, message: str, status_code: int) -> None:
    """Raise the shared Ask application error from orchestration helpers."""
    raise GroundedQueryError(code, message, status_code)
