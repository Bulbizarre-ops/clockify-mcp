/**
 * Workspace Clockify plan gate — filters tools by minPlan.
 * "all" disables filtering (expose every registered tool regardless of minPlan).
 */

export type ClockifyPlan = "free" | "standard" | "pro" | "all";
export type ToolMinPlan = "free" | "standard" | "pro";

const PLANS = new Set<ClockifyPlan>(["free", "standard", "pro", "all"]);

const RANK: Record<ToolMinPlan, number> = {
  free: 0,
  standard: 1,
  pro: 2,
};

export function parseClockifyPlan(raw: string | undefined | null): ClockifyPlan {
  const value = (raw ?? "").trim().toLowerCase();
  if (!value) return "all";
  if (PLANS.has(value as ClockifyPlan)) return value as ClockifyPlan;
  return "all";
}

/** Whether a workspace plan includes a tool that requires `minPlan`. */
export function planIncludes(plan: ClockifyPlan, minPlan: ToolMinPlan): boolean {
  if (plan === "all") return true;
  return RANK[plan] >= RANK[minPlan];
}
