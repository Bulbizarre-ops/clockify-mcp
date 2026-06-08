# Clockify MCP — Feature-Availability Error Recognition Design

**Date:** 2026-06-07
**Status:** Approved
**Author:** Alan (tracegazer)

## 1. Overview

When a Clockify operation fails, the server currently raises a bare `ClockifyAPIError` (status + raw message). Live testing showed three recurring, distinct failure modes that an agent/user must handle differently — but the raw error doesn't distinguish them:

- **Paid plan missing** — the workspace's plan doesn't include the feature (e.g. expenses on FREE returns `400 "Sin suscripción activa"`; other endpoints return `402`).
- **Feature not enabled / no permission** — the plan entitles the feature, but the module is turned off in Workspace Settings, or the API key's user lacks the role. Both surface as `403 {"code":501,"message":"Access Denied"}` (indistinguishable from each other).
- **Authentication** — `401` (missing/invalid/revoked key).

This feature classifies these at the error boundary and attaches an actionable hint, and documents the same "rules" in the server `INSTRUCTIONS` so the agent interprets them consistently. It does not attempt to name the specific Clockify feature (the 403 is genuinely ambiguous between "module off" and "no permission").

## 2. Classifier

New module `src/clockify_mcp/errors.py`:

- `ErrorCategory` — string enum: `AUTH`, `PLAN_REQUIRED`, `ACCESS_DENIED`.
- `classify_error(status_code: int, message: str) -> tuple[ErrorCategory | None, str | None]` — a pure function returning `(category, hint)` or `(None, None)`. Rules, evaluated in order:
  1. `message` contains `"suscrip"` or `"subscription"` (case-insensitive) → `PLAN_REQUIRED`. (Catches the `400 "Sin suscripción activa"` case regardless of status.)
  2. `status_code == 402` → `PLAN_REQUIRED`.
  3. `status_code == 401` → `AUTH`.
  4. `status_code == 403` → `ACCESS_DENIED`.
  5. otherwise → `(None, None)`.

Hints (English, repo convention):
- `PLAN_REQUIRED`: `"This Clockify feature isn't included in the workspace's current plan — upgrade it (e.g. Standard or Pro)."`
- `ACCESS_DENIED`: `"Access denied — either the feature isn't enabled for this workspace (enable it in Clockify → Workspace Settings) or the API key's user lacks the required role/permission."`
- `AUTH`: `"Authentication failed — the API key is missing, invalid, or revoked (check CLOCKIFY_API_KEY)."`

The classifier is pure and independent (no httpx/config imports), so it is unit-testable in isolation.

## 3. ClockifyAPIError changes (`client.py`)

`ClockifyAPIError.__init__` gains two keyword-only params, `category` and `hint`, stored as attributes (default `None`). The exception's display string keeps its current prefix and appends the hint when present:

- Without hint (unchanged): `"Clockify API error 400: Se requiere el nombre del cliente"`
- With hint: `"Clockify API error 403: Access Denied [ACCESS_DENIED] Access denied — either the feature isn't enabled ..."`

`ClockifyClient._raise_for_error` computes `category, hint = classify_error(status_code, sanitized_message)` and passes them through. Everything else is unchanged: `status_code`, `body`, and secret sanitization/length-capping all behave as today. Because the original message remains a substring of the display string, the gated live-smoke helper (`_skip_if_feature_unavailable`, which checks `status_code` and the `"suscrip"/"subscription"` substring) keeps working unchanged.

## 4. Server INSTRUCTIONS

Add one short paragraph to `server.INSTRUCTIONS` stating the rules so the agent reacts consistently:

- `PLAN_REQUIRED` (402 / "subscription") → tell the user the workspace plan doesn't include this feature; they must upgrade (Standard/Pro). Do not retry.
- `ACCESS_DENIED` (403) → the feature may be disabled in Workspace Settings (have an admin enable it) or the API key's user lacks the role; surface both possibilities. Do not retry.
- `AUTH` (401) → the API key is missing/invalid/revoked.

## 5. Testing

- `tests/test_errors.py` (new): `classify_error` for each rule and precedence (subscription message wins over status; 402, 401, 403 mappings; unmatched → `(None, None)`); hint strings present per category.
- `tests/test_client.py`: a `ClockifyAPIError` from a 403 carries `.category == ErrorCategory.ACCESS_DENIED` and `.hint`, and the hint appears in `str(exc)`; a 402/subscription error → `PLAN_REQUIRED`; a normal 400 (e.g. validation) → `category is None` and the message is unchanged in shape. Existing sanitization/retry tests still pass.
- `tests/test_server.py`: `INSTRUCTIONS` contains the rule keywords (e.g. `PLAN_REQUIRED` / "Workspace Settings" / the three categories).

## 6. Out of scope

- Naming the specific Clockify feature in the hint (per-domain wiring; the 403 is ambiguous anyway).
- Distinguishing "module disabled" from "insufficient role" within `ACCESS_DENIED` (the API returns the same `403 code 501` for both — the hint names both).
- `404` handling: left as a normal "not found" (most 404s are bad IDs, not feature gating) — no category.
- Any retry/behavioral change; this is purely classification + guidance.
