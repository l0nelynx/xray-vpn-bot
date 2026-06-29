import { createJsonClient } from "@xray/api";

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
        window.location.href = "/bot/dashboard/login";
      }
    }
  },
});

export { ApiError } from "@xray/api";
