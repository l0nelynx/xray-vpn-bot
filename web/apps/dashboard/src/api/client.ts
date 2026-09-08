import { ApiError, createJsonClient } from "@xray/api";

const API_BASE = "/bot/dashboard/api";

let _redirecting = false;

function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export const api = createJsonClient({
  base: API_BASE,
  getHeaders: () => {
    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  },
  onError: (status) => {
    if (status === 401) {
      clearToken();
      if (!_redirecting) {
        _redirecting = true;
        const next =
          window.location.pathname.replace(/^\/bot\/dashboard/, "") +
          window.location.search;
        window.location.href = `/bot/dashboard/login?next=${encodeURIComponent(next || "/")}`;
      }
    }
  },
});

export { ApiError };

/** Fetches an attachment as a blob with the same Bearer-token auth as `api` —
 * a plain <img src> can't carry Authorization headers, so callers build an
 * object URL from this instead (see useAuthedImage). */
export async function fetchAuthedBlob(url: string): Promise<Blob> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${url}`, { headers });
  if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  return res.blob();
}
