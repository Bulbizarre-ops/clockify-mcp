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
    status_code: int, message: object
) -> tuple[ErrorCategory | None, str | None]:
    """Map an API failure to (category, hint), or (None, None) if not a known case.

    A "subscription"/"suscripción" message means the plan lacks the feature, even when
    the status is 400 (Clockify returns 400 "Sin suscripción activa" for expenses), so
    that rule is checked first. ``message`` is whatever the error body yielded — it may
    not be a string (a malformed body could nest it), so non-strings are treated as
    empty rather than crashing the error path.
    """
    lowered = (message if isinstance(message, str) else "").lower()
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
