import { describe, expect, it } from "vitest";
import {
  parseClockifyPlan,
  planIncludes,
} from "../src/clockify/plan.js";

describe("parseClockifyPlan", () => {
  it("defaults empty/invalid to all", () => {
    expect(parseClockifyPlan(undefined)).toBe("all");
    expect(parseClockifyPlan("")).toBe("all");
    expect(parseClockifyPlan("enterprise")).toBe("all");
  });

  it("accepts free, standard, pro, all", () => {
    expect(parseClockifyPlan("free")).toBe("free");
    expect(parseClockifyPlan("Standard")).toBe("standard");
    expect(parseClockifyPlan("PRO")).toBe("pro");
    expect(parseClockifyPlan("all")).toBe("all");
  });
});

describe("planIncludes", () => {
  it("all includes every minPlan", () => {
    expect(planIncludes("all", "free")).toBe(true);
    expect(planIncludes("all", "standard")).toBe(true);
    expect(planIncludes("all", "pro")).toBe(true);
  });

  it("ranks free < standard < pro", () => {
    expect(planIncludes("free", "free")).toBe(true);
    expect(planIncludes("free", "standard")).toBe(false);
    expect(planIncludes("free", "pro")).toBe(false);
    expect(planIncludes("standard", "free")).toBe(true);
    expect(planIncludes("standard", "standard")).toBe(true);
    expect(planIncludes("standard", "pro")).toBe(false);
    expect(planIncludes("pro", "pro")).toBe(true);
  });
});
