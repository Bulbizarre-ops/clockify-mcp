import { describe, expect, it } from "vitest";
import { propsFromConsentForm } from "../src/oauth/auth-handler.js";
import {
  decodeOAuthState,
  encodeOAuthState,
} from "../src/oauth/pages.js";
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

describe("oauth state codec", () => {
  it("round-trips with base64url (no + / =)", () => {
    const payload = {
      responseType: "code",
      clientId: "abc",
      redirectUri: "https://claude.ai/api/mcp/auth_callback",
      scope: ["openid"],
      state: "x+y/z=",
      codeChallenge: "abc+def/ghi=",
    };
    const encoded = encodeOAuthState(payload);
    expect(encoded).not.toMatch(/[+/=]/);
    expect(decodeOAuthState(encoded)).toEqual(payload);
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
      plan: "free",
      workspaceId: "ws-1",
    });
  });

  it("honors plan from form or defaults", () => {
    const form = new FormData();
    form.set("api_key", "k");
    form.set("plan", "pro");
    expect(propsFromConsentForm(form, {})?.plan).toBe("pro");

    const form2 = new FormData();
    form2.set("api_key", "k");
    expect(propsFromConsentForm(form2, { plan: "standard" })?.plan).toBe(
      "standard",
    );
  });
});
