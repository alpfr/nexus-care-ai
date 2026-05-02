/**
 * Thin typed wrapper around fetch().
 *
 * All API calls go through here. Centralizing them gives us:
 *   - One place to attach the Authorization header
 *   - One place to translate non-2xx responses into typed errors
 *   - A single base URL that respects the rewrite proxy in next.config.ts
 *
 * Because next.config.ts proxies /api/* to the FastAPI backend, browser
 * fetches use the same origin as the page. No CORS, no preflights.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly raw?: unknown,
  ) {
    super(`API error ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, signal } = opts;

  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
    credentials: "same-origin",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload: unknown = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      isJson && typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : typeof payload === "string"
          ? payload
          : "Request failed";
    throw new ApiError(response.status, detail, payload);
  }

  return payload as T;
}

// ---------------------------------------------------------------------------
// Typed endpoint helpers
// ---------------------------------------------------------------------------
export interface LoginRequest {
  facility_code: string;
  pin: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface MeResponse {
  id: number;
  full_name: string;
  role: string;
  tenant_id: number;
  tenant_state: string;
}

export interface HealthResponse {
  status: string;
  database: string;
}

export interface RequestActivationResponse {
  tenant_id: number;
  state: string;
  activation_requested_at: string | null;
  message: string;
}

export const api = {
  health: (signal?: AbortSignal) =>
    request<HealthResponse>("/api/health", { signal }),

  login: (payload: LoginRequest, signal?: AbortSignal) =>
    request<LoginResponse>("/api/login", {
      method: "POST",
      body: payload,
      signal,
    }),

  me: (token: string, signal?: AbortSignal) =>
    request<MeResponse>("/api/me", { token, signal }),

  requestActivation: (token: string, signal?: AbortSignal) =>
    request<RequestActivationResponse>("/api/me/tenant/request-activation", {
      method: "POST",
      token,
      signal,
    }),
};
