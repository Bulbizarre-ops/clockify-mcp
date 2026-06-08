"""Clockify MCP server."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("clockify-mcp")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
