from clockify_mcp.pagination import page_params, is_last_page


def test_page_params_drops_none():
    assert page_params(None, None) == {}
    assert page_params(2, 50) == {"page": 2, "page-size": 50}
    assert page_params(2, None) == {"page": 2}


def test_is_last_page_reads_header():
    assert is_last_page({"Last-Page": "true"}) is True
    assert is_last_page({"Last-Page": "false"}) is False
    assert is_last_page({}) is True  # no header => assume done
