import { describe, expect, it } from "vitest";
import { propsFromConsentForm } from "../src/oauth/auth-handler.js";
import { escapeHtml, isHttpUrl } from "../src/oauth/types.js";

describe("escapeHtml", () => {
  it("escapes HTML special characters", () => {
    expect(escapeHtml(`<script>"x"&'y'</script>`)).toBe(
      "&lt;script&gt;&quot;x&quot;&amp;&#39;y&#39;&lt;/script&gt;",
    );
  });
});

describe("isHttpUrl", () => {
  it("allows http(s) only", () => {
    expect(isHttpUrl("https://claude.ai")).toBe(true);
    expect(isHttpUrl("javascript:alert(1)")).toBe(false);
  });
});

describe("propsFromConsentForm", () => {
  it("returns null without api_key", () => {
    const form = new FormData();
    expect(propsFromConsentForm(form, {})).toBeNull();
  });

  it("parses api key, mode, region, workspace", () => {
    const form = new FormData();
    form.set("api_key", " clockify-secret ");
    form.set("access_mode", "full");
    form.set("region", "euc1");
    form.set("workspace_id", "ws-1");
    expect(propsFromConsentForm(form, {})).toEqual({
      apiKey: "clockify-secret",
      accessMode: "full",
      region: "euc1",
      workspaceId: "ws-1",
    });
  });
});
