from clockify_mcp.bodies import drop_none, ids_filter


def test_ids_filter_shape():
    assert ids_filter(["u1", "u2"]) == {
        "ids": ["u1", "u2"],
        "contains": "CONTAINS",
        "status": "ALL",
    }


def test_drop_none_keeps_falsy_but_drops_none():
    assert drop_none({"a": None, "b": False, "c": 0, "d": "x"}) == {
        "b": False,
        "c": 0,
        "d": "x",
    }
