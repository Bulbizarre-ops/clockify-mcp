"""Helpers for building JSON request bodies for write endpoints."""

from __future__ import annotations

from typing import Any


def drop_none(values: dict[str, Any]) -> dict[str, Any]:
    """Return values without keys whose value is None.

    Clockify write bodies are JSON; omit unset fields rather than sending null.
    """
    return {k: v for k, v in values.items() if v is not None}


def ids_filter(ids: list[str]) -> dict[str, Any]:
    """Build the {ids, contains, status} filter Clockify uses to target members.

    Used for the ``users``/``userGroups`` fields of time-off policies and holidays.
    """
    return {"ids": ids, "contains": "CONTAINS", "status": "ALL"}
