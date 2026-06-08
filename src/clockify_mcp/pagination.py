"""Pagination helpers for Clockify list endpoints (page / page-size + Last-Page)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

DEFAULT_FETCH_ALL_PAGE_SIZE = 50
DEFAULT_FETCH_ALL_MAX_PAGES = 200


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


async def fetch_all_pages(
    fetch_page: Callable[[int, int], Awaitable[Any]],
    *,
    page_size: int | None = None,
    max_pages: int = DEFAULT_FETCH_ALL_MAX_PAGES,
) -> list[Any]:
    """Accumulate every page of a list endpoint into one list.

    ``fetch_page(page, page_size)`` is awaited with 1-indexed pages until it returns an
    empty page or a short page (fewer than ``page_size`` items), which marks the end.
    Clockify list endpoints return plain lists and ``client.get`` does not surface the
    ``Last-Page`` header, so the short/empty-batch heuristic is what we have; ``max_pages``
    bounds it as a safety net against an endpoint that never returns a short page.
    """
    size = page_size or DEFAULT_FETCH_ALL_PAGE_SIZE
    results: list[Any] = []
    for page in range(1, max_pages + 1):
        batch = await fetch_page(page, size)
        if not batch:
            break
        results.extend(batch)
        if len(batch) < size:
            break
    return results
