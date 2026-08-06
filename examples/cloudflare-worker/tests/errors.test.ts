import { describe, expect, it } from "vitest";
import { classifyError } from "../src/clockify/errors.js";

describe("classifyError", () => {
  it("treats subscription messages as PLAN_REQUIRED regardless of status", () => {
    const [cat, hint] = classifyError(400, "Sin suscripción activa.");
    expect(cat).toBe("PLAN_REQUIRED");
    expect(hint?.toLowerCase()).toContain("plan");
  });

  it("detects English subscription wording", () => {
    const [cat] = classifyError(400, "No active subscription");
    expect(cat).toBe("PLAN_REQUIRED");
  });

  it("maps 402 to PLAN_REQUIRED", () => {
    const [cat, hint] = classifyError(402, "Payment required");
    expect(cat).toBe("PLAN_REQUIRED");
    expect(hint).toBeTruthy();
  });

  it("maps 401 to AUTH", () => {
    const [cat, hint] = classifyError(401, "Api key does not exist");
    expect(cat).toBe("AUTH");
    expect(hint?.toLowerCase()).toContain("key");
  });

  it("maps 403 to ACCESS_DENIED", () => {
    const [cat, hint] = classifyError(403, "Access Denied");
    expect(cat).toBe("ACCESS_DENIED");
    expect(hint?.toLowerCase()).toContain("workspace settings");
  });

  it("gives subscription precedence over status", () => {
    const [cat] = classifyError(403, "No active subscription");
    expect(cat).toBe("PLAN_REQUIRED");
  });

  it("leaves plain validation errors unclassified", () => {
    const [cat, hint] = classifyError(400, "Se requiere el nombre del cliente");
    expect(cat).toBeNull();
    expect(hint).toBeNull();
  });

  it("leaves 404 unclassified", () => {
    expect(classifyError(404, "Not found")).toEqual([null, null]);
  });

  it("does not crash on non-string messages", () => {
    expect(classifyError(400, { nested: "x" })).toEqual([null, null]);
    const [cat, hint] = classifyError(403, ["a", "b"]);
    expect(cat).toBe("ACCESS_DENIED");
    expect(hint).toBeTruthy();
  });
});
