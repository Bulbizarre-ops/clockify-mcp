from clockify_mcp.errors import ErrorCategory, classify_error


def test_subscription_message_is_plan_required_regardless_of_status():
    cat, hint = classify_error(400, "Sin suscripción activa.")
    assert cat is ErrorCategory.PLAN_REQUIRED
    assert "plan" in hint.lower()


def test_subscription_word_english():
    cat, _ = classify_error(400, "No active subscription")
    assert cat is ErrorCategory.PLAN_REQUIRED


def test_402_is_plan_required():
    cat, hint = classify_error(402, "Payment required")
    assert cat is ErrorCategory.PLAN_REQUIRED
    assert hint


def test_401_is_auth():
    cat, hint = classify_error(401, "Api key does not exist")
    assert cat is ErrorCategory.AUTH
    assert "key" in hint.lower()


def test_403_is_access_denied():
    cat, hint = classify_error(403, "Access Denied")
    assert cat is ErrorCategory.ACCESS_DENIED
    assert "workspace settings" in hint.lower()


def test_subscription_takes_precedence_over_status():
    # a 403 whose message mentions subscription is a plan problem, not access
    cat, _ = classify_error(403, "No active subscription")
    assert cat is ErrorCategory.PLAN_REQUIRED


def test_plain_validation_error_is_unclassified():
    cat, hint = classify_error(400, "Se requiere el nombre del cliente")
    assert cat is None
    assert hint is None


def test_404_is_unclassified():
    assert classify_error(404, "Not found") == (None, None)


def test_non_string_message_does_not_crash():
    # a malformed error body could yield a non-string message; must not raise
    assert classify_error(400, {"nested": "x"}) == (None, None)
    cat, hint = classify_error(403, ["a", "b"])
    assert cat is ErrorCategory.ACCESS_DENIED
    assert hint


def test_category_values_are_plain_strings():
    assert ErrorCategory.ACCESS_DENIED.value == "ACCESS_DENIED"
