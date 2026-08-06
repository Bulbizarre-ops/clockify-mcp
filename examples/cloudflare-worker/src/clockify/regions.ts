export type ClockifyRegion = "global" | "euc1" | "use2" | "euw2" | "apse2";

const REGIONS = new Set<ClockifyRegion>([
  "global",
  "euc1",
  "use2",
  "euw2",
  "apse2",
]);

export function parseRegion(raw: string | undefined | null): ClockifyRegion {
  const value = (raw ?? "").trim().toLowerCase();
  if (REGIONS.has(value as ClockifyRegion)) return value as ClockifyRegion;
  return "global";
}

export function resolveHosts(region: ClockifyRegion): {
  regularBase: string;
  reportsBase: string;
} {
  if (region === "global") {
    return {
      regularBase: "https://api.clockify.me/api/v1",
      reportsBase: "https://reports.api.clockify.me/v1",
    };
  }
  return {
    regularBase: `https://${region}.clockify.me/api/v1`,
    reportsBase: `https://${region}.clockify.me/report/v1`,
  };
}
