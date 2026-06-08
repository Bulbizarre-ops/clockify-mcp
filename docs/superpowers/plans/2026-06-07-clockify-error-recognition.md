# Feature-Availability Error Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify Clockify API failures into `PLAN_REQUIRED` / `ACCESS_DENIED` / `AUTH` with an actionable hint on `ClockifyAPIError`, and document the same rules in the server `INSTRUCTIONS`.

**Architecture:** A pure classifier in a new `errors.py` maps (status_code, message) → (category, hint). `ClockifyClient._raise_for_error` runs it and attaches `category`/`hint` to the raised `ClockifyAPIError`, whose display string appends the hint. Server `INSTRUCTIONS` gains a short rules paragraph so the agent reacts consistently.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx + pytest-asyncio, `uv`, ruff.

---

## Background — verified current state

- `src/clockify_mcp/client.py`:
  - `ClockifyAPIError(Exception).__init__(self, status_code, message, body=None)` → `super().__init__(f"Clockify API error {status_code}: {message}")`, stores `status_code`, `body`.
  - `_raise_for_error(self, response)` parses `body`/`message`, then `raise ClockifyAPIError(response.status_code, self._sanitize(message), self._sanitize(body))`. Used by both `_handle` and `_handle_bytes`.
  - `_sanitize` redacts secrets and caps length; it preserves words like "subscription"/"suscripción".
- `tests/test_live_smoke.py::_skip_if_feature_unavailable` checks `exc.status_code in (402,403,404)` or (`400` and `"suscrip"/"subscription"` in `str(exc).lower()`). The original message stays a substring of the new display string, so this keeps working.
- Verified failure signals from live testing: expenses on FREE → `400 "Sin suscripción activa"`; other premium endpoints on FREE → `402`/`403`/`404`; premium endpoints on PRO with the module OFF → `403 {"code":501,"message":"Access Denied"}`; bad key → `401`.

**Baseline:** `uv run pytest -q` → 176 passed, 16 skipped, ruff clean.

---

## File Structure

- Create: `src/clockify_mcp/errors.py` — `ErrorCategory` enum + `classify_error()` (pure, no deps)
- Modify: `src/clockify_mcp/client.py` — `ClockifyAPIError` gains `category`/`hint`; `_raise_for_error` classifies
- Modify: `src/clockify_mcp/server.py` — `INSTRUCTIONS` rules paragraph
- Create: `tests/test_errors.py`
- Modify: `tests/test_client.py`, `tests/test_server.py`

---

## Task 1: Error classifier

**Files:** Create `src/clockify_mcp/errors.py`; Test `tests/test_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_errors.py`:

```python
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


def test_category_values_are_plain_strings():
    assert ErrorCategory.ACCESS_DENIED.value == "ACCESS_DENIED"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_errors.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_mcp.errors'`.

- [ ] **Step 3: Implement the classifier**

Create `src/clockify_mcp/errors.py`:

```python
"""Classify Clockify API failures into actionable categories.

Pure helpers (no httpx/config deps) so they're trivially unit-testable. Used by the
client to annotate ClockifyAPIError with a category + hint, and mirrored as rules in
the server INSTRUCTIONS.
"""

from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    AUTH = "AUTH"
    PLAN_REQUIRED = "PLAN_REQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"


_HINTS: dict[ErrorCategory, str] = {
    ErrorCategory.PLAN_REQUIRED: (
        "This Clockify feature isn't included in the workspace's current plan — "
        "upgrade it (e.g. Standard or Pro)."
    ),
    ErrorCategory.ACCESS_DENIED: (
        "Access denied — either the feature isn't enabled for this workspace (enable "
        "it in Clockify → Workspace Settings) or the API key's user lacks the required "
        "role/permission."
    ),
    ErrorCategory.AUTH: (
        "Authentication failed — the API key is missing, invalid, or revoked (check "
        "CLOCKIFY_API_KEY)."
    ),
}


def classify_error(
    status_code: int, message: str
) -> tuple[ErrorCategory | None, str | None]:
    """Map an API failure to (category, hint), or (None, None) if not a known case.

    A "subscription"/"suscripción" message means the plan lacks the feature, even when
    the status is 400 (Clockify returns 400 "Sin suscripción activa" for expenses), so
    that rule is checked first.
    """
    lowered = (message or "").lower()
    if "suscrip" in lowered or "subscription" in lowered:
        category = ErrorCategory.PLAN_REQUIRED
    elif status_code == 402:
        category = ErrorCategory.PLAN_REQUIRED
    elif status_code == 401:
        category = ErrorCategory.AUTH
    elif status_code == 403:
        category = ErrorCategory.ACCESS_DENIED
    else:
        return None, None
    return category, _HINTS[category]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_errors.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (185 passed, 16 skipped) and ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/errors.py tests/test_errors.py
git commit -m "feat: classify_error — map API failures to PLAN_REQUIRED/ACCESS_DENIED/AUTH"
```

---

## Task 2: Wire classification into ClockifyAPIError

**Files:** Modify `src/clockify_mcp/client.py`; Test `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_client.py` (it already imports `httpx`, `respx`, `ClockifyClient`, `config`; add the imports shown):

```python
import pytest

from clockify_mcp.client import ClockifyAPIError
from clockify_mcp.errors import ErrorCategory


@respx.mock
async def test_403_error_is_access_denied_with_hint(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/x").mock(
        return_value=httpx.Response(403, json={"message": "Access Denied", "code": 501})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.get("workspaces/ws1/x")
    exc = ei.value
    assert exc.category is ErrorCategory.ACCESS_DENIED
    assert exc.hint and "Workspace Settings" in exc.hint
    assert "[ACCESS_DENIED]" in str(exc)
    assert "Access Denied" in str(exc)  # original message preserved
    await client.aclose()


@respx.mock
async def test_400_subscription_is_plan_required(config):
    respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories").mock(
        return_value=httpx.Response(400, json={"message": "Sin suscripción activa."})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.post("workspaces/ws1/expenses/categories", json={"name": "x"})
    assert ei.value.category is ErrorCategory.PLAN_REQUIRED
    await client.aclose()


@respx.mock
async def test_plain_validation_error_has_no_category(config):
    respx.put("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(400, json={"message": "Se requiere el nombre del cliente"})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.put("workspaces/ws1/clients/c1", json={})
    exc = ei.value
    assert exc.category is None
    assert exc.hint is None
    assert str(exc) == "Clockify API error 400: Se requiere el nombre del cliente"
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_client.py -q`
Expected: FAIL — `AttributeError: 'ClockifyAPIError' object has no attribute 'category'`.

- [ ] **Step 3: Update `ClockifyAPIError`**

In `src/clockify_mcp/client.py`, replace the class:

```python
class ClockifyAPIError(Exception):
    """Raised when the Clockify API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        super().__init__(f"Clockify API error {status_code}: {message}")
        self.status_code = status_code
        self.body = body
```

with:

```python
class ClockifyAPIError(Exception):
    """Raised when the Clockify API returns a non-2xx response.

    category/hint are set by classify_error when the failure matches a known case
    (plan missing, feature/permission, auth); they are None for plain errors.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        body: Any = None,
        *,
        category: "ErrorCategory | None" = None,
        hint: str | None = None,
    ):
        display = f"Clockify API error {status_code}: {message}"
        if hint:
            display = f"{display} [{category.value}] {hint}"
        super().__init__(display)
        self.status_code = status_code
        self.body = body
        self.category = category
        self.hint = hint
```

- [ ] **Step 4: Import the classifier and use it in `_raise_for_error`**

In `src/clockify_mcp/client.py`, add to the imports near the top (after `from .config import Config`):

```python
from .errors import ErrorCategory, classify_error
```

Then replace `_raise_for_error`:

```python
    def _raise_for_error(self, response: httpx.Response) -> None:
        try:
            body = response.json()
            message = body.get("message") or body.get("error") or response.text
        except Exception:
            body = response.text
            message = response.text
        sanitized = self._sanitize(message)
        category, hint = classify_error(response.status_code, sanitized)
        raise ClockifyAPIError(
            response.status_code,
            sanitized,
            self._sanitize(body),
            category=category,
            hint=hint,
        )
```

(`ErrorCategory` is imported so the type annotation in `ClockifyAPIError` resolves; it's a real import, not just for typing.)

- [ ] **Step 5: Run the client tests**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS (existing + 3 new).

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (188 passed, 16 skipped) and ruff clean. In particular the existing sanitize/retry tests and `test_live_smoke` collection are unaffected.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/client.py tests/test_client.py
git commit -m "feat: attach category/hint to ClockifyAPIError via classify_error"
```

---

## Task 3: Document the rules in server INSTRUCTIONS

**Files:** Modify `src/clockify_mcp/server.py`; Test `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server.py`:

```python
def test_instructions_describe_error_categories():
    from clockify_mcp.server import INSTRUCTIONS

    assert "PLAN_REQUIRED" in INSTRUCTIONS
    assert "ACCESS_DENIED" in INSTRUCTIONS
    assert "Workspace Settings" in INSTRUCTIONS
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_server.py::test_instructions_describe_error_categories -q`
Expected: FAIL — assertion error (`PLAN_REQUIRED` not in INSTRUCTIONS).

- [ ] **Step 3: Add the rules paragraph to INSTRUCTIONS**

In `src/clockify_mcp/server.py`, the `INSTRUCTIONS` string is a backslash-line-continued block ending with the `DISAMBIGUATION:` paragraph. Insert a new paragraph immediately before the `DISAMBIGUATION:` paragraph (keep the trailing `\` on every line and a blank line between paragraphs):

```python
ERRORS: when a tool fails, a ClockifyAPIError carries a category that tells you what \
to do. PLAN_REQUIRED (402, or a "subscription" message) — the workspace's plan does \
not include this feature; tell the user to upgrade it (e.g. Standard/Pro); do not \
retry. ACCESS_DENIED (403) — the feature is not enabled for this workspace (an admin \
must enable it in Clockify → Workspace Settings) OR the API key's user lacks the \
required role; surface both possibilities; do not retry. AUTH (401) — the API key is \
missing, invalid, or revoked. Always relay the cause to the user instead of retrying \
blindly.

```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_server.py::test_instructions_describe_error_categories -q`
Expected: PASS.

- [ ] **Step 5: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (189 passed, 16 skipped) and ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/server.py tests/test_server.py
git commit -m "docs: document API error categories (plan/feature/auth) in server INSTRUCTIONS"
```

---

## Self-Review

**Spec coverage:**
- §2 classifier (`errors.py`, rules + precedence, hints) → Task 1 ✓
- §3 `ClockifyAPIError` `category`/`hint` + `_raise_for_error` classifying on the sanitized message; status/body/sanitize preserved → Task 2 ✓
- §4 INSTRUCTIONS rules paragraph → Task 3 ✓
- §5 tests: classifier unit tests, client error attrs/string, INSTRUCTIONS keywords, existing behavior preserved → Tasks 1–3 ✓
- §6 out of scope (no per-domain feature naming, no 404 gating, no retry change) — honored: 404 returns (None, None); no behavioral change ✓

**Placeholder scan:** none — every code/test step shows full code; commands show expected output.

**Type/name consistency:** `ErrorCategory` (str enum) + `classify_error` names match across `errors.py`, `client.py`, and tests; `category.value` used for the display string (a `(str, Enum)` member's `f"{m}"` would render `ErrorCategory.X`, so `.value` is required and is what the test `[ACCESS_DENIED]` asserts). `_skip_if_feature_unavailable` still matches because the original message remains in the display string and `status_code` is unchanged. Test-count figures are estimates; the implementer confirms actual counts at each step.
