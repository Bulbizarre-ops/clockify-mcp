import { describe, expect, it } from "vitest";
import { parseRegion, resolveHosts } from "../src/clockify/regions.js";

describe("parseRegion", () => {
  it("defaults to global", () => {
    expect(parseRegion(undefined)).toBe("global");
    expect(parseRegion("")).toBe("global");
  });

  it("accepts known regions", () => {
    for (const region of ["global", "euc1", "use2", "euw2", "apse2"] as const) {
      expect(parseRegion(region)).toBe(region);
    }
  });

  it("falls back to global for unknown regions", () => {
    expect(parseRegion("eu-west-1")).toBe("global");
  });
});

describe("resolveHosts", () => {
  it("uses global API + reports hosts by default", () => {
    expect(resolveHosts("global")).toEqual({
      regularBase: "https://api.clockify.me/api/v1",
      reportsBase: "https://reports.api.clockify.me/v1",
    });
  });

  it("uses regional hosts for non-global regions", () => {
    expect(resolveHosts("euc1")).toEqual({
      regularBase: "https://euc1.clockify.me/api/v1",
      reportsBase: "https://euc1.clockify.me/report/v1",
    });
  });
});
