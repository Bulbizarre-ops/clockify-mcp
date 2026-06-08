"""Pagination helpers for Clockify list endpoints (page / page-size + Last-Page)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def page_params(page: int | None, page_size: int | None) -> dict[str, Any]:
    """Build query params for a paginated GET, dropping unset values.

    Clockify uses 1-indexed ``page`` and a hyphenated ``page-size``.
    """
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["page-size"] = page_size
    return params


def is_last_page(headers: Mapping[str, str]) -> bool:
    """Interpret the custom ``Last-Page`` response header.

    Missing header is treated as the last page (single-shot responses).
    """
    value = headers.get("Last-Page")
    if value is None:
        return True
    return value.strip().lower() == "true"
