import {
  parseAccessMode,
  type AccessMode,
} from "../clockify/access-mode.js";
import { parseClockifyPlan, type ClockifyPlan } from "../clockify/plan.js";
import { parseRegion, type ClockifyRegion } from "../clockify/regions.js";

export type ClockifyCredentials = {
  apiKey: string;
  accessMode: AccessMode;
  region: ClockifyRegion;
  plan: ClockifyPlan;
  workspaceId?: string;
};

export type CredentialDefaults = {
  defaultAccessMode?: string;
  defaultRegion?: string;
  defaultPlan?: string;
};

/**
 * Extract per-request Clockify credentials from HTTP headers.
 * The Worker never stores the API key.
 */
export function extractClockifyCredentials(
  request: Request,
  defaults: CredentialDefaults = {},
): ClockifyCredentials | null {
  const auth = request.headers.get("Authorization");
  let apiKey: string | undefined;
  if (auth?.toLowerCase().startsWith("bearer ")) {
    apiKey = auth.slice(7).trim();
  }
  if (!apiKey) {
    apiKey = request.headers.get("X-Api-Key")?.trim() || undefined;
  }
  if (!apiKey) return null;

  const modeHeader = request.headers.get("X-Clockify-Access-Mode");
  const regionHeader = request.headers.get("X-Clockify-Region");
  const planHeader = request.headers.get("X-Clockify-Plan");
  const workspaceId =
    request.headers.get("X-Clockify-Workspace-Id")?.trim() || undefined;

  return {
    apiKey,
    accessMode: parseAccessMode(modeHeader ?? defaults.defaultAccessMode),
    region: parseRegion(regionHeader ?? defaults.defaultRegion),
    plan: parseClockifyPlan(planHeader ?? defaults.defaultPlan),
    workspaceId,
  };
}
