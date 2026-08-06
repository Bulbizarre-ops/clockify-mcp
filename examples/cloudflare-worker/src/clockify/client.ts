import { resolveHosts, type ClockifyRegion } from "./regions.js";

export type ClockifyClientOptions = {
  apiKey: string;
  region: ClockifyRegion;
  defaultWorkspaceId?: string;
  fetchImpl?: typeof fetch;
};

export class ClockifyAPIError extends Error {
  readonly statusCode: number;
  readonly body: unknown;

  constructor(statusCode: number, message: string, body: unknown = null) {
    super(`Clockify API error ${statusCode}: ${message}`);
    this.name = "ClockifyAPIError";
    this.statusCode = statusCode;
    this.body = body;
  }
}

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function withQuery(
  url: string,
  params?: Record<string, string | number | boolean | undefined | null>,
): string {
  if (!params) return url;
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    qs.set(key, String(value));
  }
  const encoded = qs.toString();
  return encoded ? `${url}?${encoded}` : url;
}

export class ClockifyClient {
  readonly defaultWorkspaceId?: string;
  private readonly apiKey: string;
  private readonly regularBase: string;
  private readonly reportsBase: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ClockifyClientOptions) {
    this.apiKey = options.apiKey;
    this.defaultWorkspaceId = options.defaultWorkspaceId;
    const hosts = resolveHosts(options.region);
    this.regularBase = hosts.regularBase;
    this.reportsBase = hosts.reportsBase;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  get(path: string, params?: Record<string, string | number | boolean | undefined | null>) {
    return this.request("GET", this.regularBase, path, { params });
  }

  post(path: string, json?: unknown) {
    return this.request("POST", this.regularBase, path, { json });
  }

  put(path: string, json?: unknown) {
    return this.request("PUT", this.regularBase, path, { json });
  }

  patch(path: string, json?: unknown) {
    return this.request("PATCH", this.regularBase, path, { json });
  }

  delete(path: string) {
    return this.request("DELETE", this.regularBase, path);
  }

  report(path: string, json?: unknown) {
    return this.request("POST", this.reportsBase, path, { json });
  }

  private async request(
    method: string,
    base: string,
    path: string,
    opts: {
      params?: Record<string, string | number | boolean | undefined | null>;
      json?: unknown;
    } = {},
  ): Promise<unknown> {
    const url = withQuery(joinUrl(base, path), opts.params);
    const headers: Record<string, string> = {
      "X-Api-Key": this.apiKey,
      Accept: "application/json",
    };
    let body: string | undefined;
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    }

    const response = await this.fetchImpl(url, { method, headers, body });
    if (response.status === 204) return null;

    const text = await response.text();
    let parsed: unknown = text;
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
    } else {
      parsed = null;
    }

    if (!response.ok) {
      const message =
        typeof parsed === "string"
          ? parsed.slice(0, 1000)
          : JSON.stringify(parsed).slice(0, 1000);
      throw new ClockifyAPIError(response.status, message || response.statusText, parsed);
    }
    return parsed;
  }
}
