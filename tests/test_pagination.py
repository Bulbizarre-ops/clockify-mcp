from clockify_mcp.pagination import fetch_all_pages, page_params, is_last_page


def test_page_params_drops_none():
    assert page_params(None, None) == {}
    assert page_params(2, 50) == {"page": 2, "page-size": 50}
    assert page_params(2, None) == {"page": 2}


def test_is_last_page_reads_header():
    assert is_last_page({"Last-Page": "true"}) is True
    assert is_last_page({"Last-Page": "false"}) is False
    assert is_last_page({}) is True  # no header => assume done


async def test_fetch_all_pages_stops_on_short_page():
    pages = {1: [1, 2], 2: [3, 4], 3: [5]}  # page 3 is short -> last page
    calls = []

    async def fetch(page, size):
        calls.append((page, size))
        return pages.get(page, [])

    result = await fetch_all_pages(fetch, page_size=2)
    assert result == [1, 2, 3, 4, 5]
    assert calls == [(1, 2), (2, 2), (3, 2)]  # stopped after the short page


async def test_fetch_all_pages_stops_on_empty_page():
    pages = {1: [1, 2], 2: [3, 4]}  # page 3 empty -> stop, no short page before it

    async def fetch(page, size):
        return pages.get(page, [])

    assert await fetch_all_pages(fetch, page_size=2) == [1, 2, 3, 4]


async def test_fetch_all_pages_default_size_and_max_pages():
    async def fetch(page, size):
        assert size == 50  # default page size
        return list(range(size))  # always a full page -> never short

    result = await fetch_all_pages(fetch, max_pages=3)
    assert len(result) == 150  # bounded by max_pages, not an infinite loop


async def test_fetch_all_pages_empty_first_page():
    async def fetch(page, size):
        return []

    assert await fetch_all_pages(fetch, page_size=10) == []
