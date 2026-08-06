import { describe, expect, it } from "vitest";
import {
  parseAccessMode,
  timeTrackingEnabled,
  writesEnabled,
} from "../src/clockify/access-mode.js";

describe("parseAccessMode", () => {
  it("defaults to read when missing or empty", () => {
    expect(parseAccessMode(undefined)).toBe("read");
    expect(parseAccessMode("")).toBe("read");
    expect(parseAccessMode("  ")).toBe("read");
  });

  it("accepts the three Python-aligned modes case-insensitively", () => {
    expect(parseAccessMode("READ")).toBe("read");
    expect(parseAccessMode("time-tracking")).toBe("time-tracking");
    expect(parseAccessMode("Full")).toBe("full");
  });

  it("falls back to read for unknown values", () => {
    expect(parseAccessMode("write")).toBe("read");
    expect(parseAccessMode("admin")).toBe("read");
  });
});

describe("mode helpers", () => {
  it("timeTrackingEnabled is true for time-tracking and full", () => {
    expect(timeTrackingEnabled("read")).toBe(false);
    expect(timeTrackingEnabled("time-tracking")).toBe(true);
    expect(timeTrackingEnabled("full")).toBe(true);
  });

  it("writesEnabled is true only for full", () => {
    expect(writesEnabled("read")).toBe(false);
    expect(writesEnabled("time-tracking")).toBe(false);
    expect(writesEnabled("full")).toBe(true);
  });
});
