export type AccessMode = "read" | "time-tracking" | "full";

const MODES = new Set<AccessMode>(["read", "time-tracking", "full"]);

export function parseAccessMode(raw: string | undefined | null): AccessMode {
  const value = (raw ?? "").trim().toLowerCase();
  if (!value) return "read";
  if (MODES.has(value as AccessMode)) return value as AccessMode;
  return "read";
}

export function timeTrackingEnabled(mode: AccessMode): boolean {
  return mode === "time-tracking" || mode === "full";
}

export function writesEnabled(mode: AccessMode): boolean {
  return mode === "full";
}
