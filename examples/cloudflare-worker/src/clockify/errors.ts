/**
 * Classify Clockify API failures into actionable categories.
 * Mirrors the Python server's clockify_mcp.errors helpers.
 */

export type ErrorCategory = "AUTH" | "PLAN_REQUIRED" | "ACCESS_DENIED";

const HINTS: Record<ErrorCategory, string> = {
  PLAN_REQUIRED:
    "This Clockify feature isn't included in the workspace's current plan — " +
    "upgrade it (e.g. Standard or Pro).",
  ACCESS_DENIED:
    "Access denied — either the feature isn't enabled for this workspace (enable " +
    "it in Clockify → Workspace Settings) or the API key's user lacks the required " +
    "role/permission.",
  AUTH:
    "Authentication failed — the API key is missing, invalid, or revoked (check " +
    "CLOCKIFY_API_KEY).",
};

/**
 * Map an API failure to [category, hint], or [null, null] if not a known case.
 *
 * A "subscription"/"suscripción" message means the plan lacks the feature, even when
 * the status is 400 (Clockify returns 400 "Sin suscripción activa" for expenses), so
 * that rule is checked first. `message` may not be a string — non-strings are treated
 * as empty rather than crashing the error path.
 */
export function classifyError(
  statusCode: number,
  message: unknown,
): [ErrorCategory | null, string | null] {
  const lowered = (typeof message === "string" ? message : "").toLowerCase();
  let category: ErrorCategory | null = null;
  if (
    lowered.includes("suscrip") ||
    lowered.includes("subscription") ||
    statusCode === 402
  ) {
    category = "PLAN_REQUIRED";
  } else if (statusCode === 401) {
    category = "AUTH";
  } else if (statusCode === 403) {
    category = "ACCESS_DENIED";
  } else {
    return [null, null];
  }
  return [category, HINTS[category]];
}
