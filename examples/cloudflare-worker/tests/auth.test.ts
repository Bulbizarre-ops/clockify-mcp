import { describe, expect, it } from "vitest";
import { extractClockifyCredentials } from "../src/auth/request-credentials.js";

function req(headers: Record<string, string>): Request {
  return new Request("https://example.test/mcp", { method: "POST", headers });
}

describe("extractClockifyCredentials", () => {
  it("reads Authorization Bearer", () => {
    const creds = extractClockifyCredentials(req({ Authorization: "Bearer secret-key" }));
    expect(creds).toEqual({
      apiKey: "secret-key",
      accessMode: "read",
      region: "global",
      workspaceId: undefined,
    });
  });

  it("reads X-Api-Key", () => {
    const creds = extractClockifyCredentials(req({ "X-Api-Key": "from-header" }));
    expect(creds?.apiKey).toBe("from-header");
  });

  it("prefers Authorization Bearer over X-Api-Key", () => {
    const creds = extractClockifyCredentials(
      req({ Authorization: "Bearer primary", "X-Api-Key": "secondary" }),
    );
    expect(creds?.apiKey).toBe("primary");
  });

  it("returns null when no API key is present", () => {
    expect(extractClockifyCredentials(req({}))).toBeNull();
  });

  it("parses optional Clockify headers", () => {
    const creds = extractClockifyCredentials(
      req({
        Authorization: "Bearer k",
        "X-Clockify-Access-Mode": "time-tracking",
        "X-Clockify-Region": "euw2",
        "X-Clockify-Workspace-Id": "ws-123",
      }),
    );
    expect(creds).toMatchObject({
      apiKey: "k",
      accessMode: "time-tracking",
      region: "euw2",
      workspaceId: "ws-123",
    });
  });

  it("applies defaults from options when headers omit mode/region", () => {
    const creds = extractClockifyCredentials(req({ "X-Api-Key": "k" }), {
      defaultAccessMode: "full",
      defaultRegion: "apse2",
    });
    expect(creds?.accessMode).toBe("full");
    expect(creds?.region).toBe("apse2");
  });
});
