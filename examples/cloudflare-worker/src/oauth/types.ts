import type { AccessMode } from "../clockify/access-mode.js";
import type { ClockifyRegion } from "../clockify/regions.js";

/** Props stored on the OAuth grant (and set on ctx.props for /mcp). */
export type ClockifyAuthProps = {
  apiKey: string;
  accessMode: AccessMode;
  region: ClockifyRegion;
  workspaceId?: string;
};

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function isHttpUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}
