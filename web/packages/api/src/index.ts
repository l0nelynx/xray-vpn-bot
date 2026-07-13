/**
 * Shared JSON-over-fetch client core for both frontends.
 *
 * The dashboard (JWT/Bearer auth, login-redirect on 401) and the miniapp
 * (Telegram init-data auth) have different auth and base paths but identical
 * request plumbing: build headers, JSON-encode the body, throw a typed error on
 * a non-2xx response, treat 204 as empty. That plumbing lives here; each app
 * supplies its specifics via {@link JsonClientOptions}.
 */

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface JsonClientOptions {
  /** Prefix prepended to every request path, e.g. "/bot/dashboard/api". */
  base: string;
  /** Per-request headers (auth). Called fresh on every request. */
  getHeaders?: () => Record<string, string>;
  /** Side effect on any non-2xx response (e.g. clear token + redirect on 401). */
  onError?: (status: number) => void;
}

export interface JsonClient {
  get: <T>(path: string, signal?: AbortSignal) => Promise<T>;
  post: <T>(path: string, body?: unknown) => Promise<T>;
  put: <T>(path: string, body?: unknown) => Promise<T>;
  patch: <T>(path: string, body?: unknown) => Promise<T>;
  delete: <T>(path: string) => Promise<T>;
  /** multipart/form-data POST — used for file uploads. No Content-Type is set
   * so the browser can add its own multipart boundary. */
  postForm: <T>(path: string, form: FormData) => Promise<T>;
}

export function createJsonClient(opts: JsonClientOptions): JsonClient {
  async function handleResponse<T>(res: Response): Promise<T> {
    if (!res.ok) {
      opts.onError?.(res.status);
      let detail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data?.detail) detail = data.detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }

    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  async function request<T>(
    method: string,
    path: string,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T> {
    const headers: Record<string, string> = { ...(opts.getHeaders?.() ?? {}) };
    if (body !== undefined) headers["Content-Type"] = "application/json";

    const res = await fetch(`${opts.base}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });

    return handleResponse<T>(res);
  }

  async function requestForm<T>(path: string, form: FormData): Promise<T> {
    const headers: Record<string, string> = { ...(opts.getHeaders?.() ?? {}) };

    const res = await fetch(`${opts.base}${path}`, {
      method: "POST",
      headers,
      body: form,
    });

    return handleResponse<T>(res);
  }

  return {
    get: <T>(path: string, signal?: AbortSignal) => request<T>("GET", path, undefined, signal),
    post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
    put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
    patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
    delete: <T>(path: string) => request<T>("DELETE", path),
    postForm: <T>(path: string, form: FormData) => requestForm<T>(path, form),
  };
}
