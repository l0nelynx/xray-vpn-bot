/**
 * JWT-based API client for the web portal.
 * All auth/data endpoints are the existing /api/android/* routes.
 * Web-specific endpoints are at /api/web/*.
 */

const API_BASE = "/bot/miniapp/api";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message?: string) {
    super(message || code);
    this.status = status;
    this.code = code;
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem("web_access_token");
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem("web_access_token", access);
  localStorage.setItem("web_refresh_token", refresh);
}

export function clearTokens(): void {
  localStorage.removeItem("web_access_token");
  localStorage.removeItem("web_refresh_token");
}

export function getRefreshToken(): string | null {
  return localStorage.getItem("web_refresh_token");
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  requireAuth = true
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (requireAuth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let code = `http_${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail?.code) code = data.detail.code;
      else if (typeof data?.detail === "string") code = data.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, code);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T>(path: string, auth = true) => request<T>("GET", path, undefined, auth);
const post = <T>(path: string, body?: unknown, auth = true) => request<T>("POST", path, body, auth);
const del = <T>(path: string) => request<T>("DELETE", path);

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface UserSummary {
  id: number;
  email: string | null;
  email_verified: boolean;
  has_password: boolean;
  has_telegram: boolean;
}

export interface AuthResponse {
  tokens: TokenPair;
  user: UserSummary;
}

export const auth = {
  login: (email: string, password: string) =>
    post<AuthResponse>("/android/auth/login", { email, password }, false),

  register: (email: string, password: string, invite_code: string) =>
    post<AuthResponse>("/web/register", { email, password, invite_code }, false),

  refresh: (refresh_token: string) =>
    post<TokenPair>("/android/auth/refresh", { refresh_token }, false),

  logout: (refresh_token: string) =>
    post<{ status: string }>("/android/auth/logout", { refresh_token }),
};

// ---------------------------------------------------------------------------
// Email verification
// ---------------------------------------------------------------------------

export const email = {
  sendCode: () => post<{ status: string }>("/android/auth/email/send-code"),
  verify: (code: string) =>
    post<{ status: string }>("/android/auth/email/verify", { code }),
};

// ---------------------------------------------------------------------------
// User data (/android/me)  — shape mirrors AndroidMeResponse in schemas_data.py
// ---------------------------------------------------------------------------

export interface AndroidUserSummary {
  id: number;
  email: string | null;
  email_verified: boolean;
  tg_id: number | null;
  language: string | null;
}

export interface SubscriptionInfo {
  tariff: string;
  status: string | null;
  days_left: number;
  expire_iso: string | null;
  data_limit_gb: number | null;
  traffic_used_gb: number;
  devices_count: number;
  subscription_url: string | null;
  source: string;
}

export interface MeResponse {
  user: AndroidUserSummary;
  subscription: SubscriptionInfo | null;
  links: {
    bot_url: string;
    policy_url: string;
    agreement_url: string;
    news_url: string;
    branding_name: string;
    support_bot_link: string;
  };
}

export const me = {
  get: () => get<MeResponse>("/android/me"),
};

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------

export interface DeviceItem {
  hwid: string;
  platform: string | null;
  os_version: string | null;
  device_model: string | null;
  user_agent: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DevicesResponse {
  total: number;
  devices: DeviceItem[];
}

export const devices = {
  list: () => get<DevicesResponse>("/android/devices"),
  remove: (hwid: string) => del<{ status: string }>(`/android/devices/${hwid}`),
};

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export interface SessionInfo {
  id: number;
  issued_at: string;
  expires_at: string;
  user_agent: string | null;
  ip: string | null;
  current: boolean | null;
}

export interface SessionsResponse {
  total: number;
  sessions: SessionInfo[];
}

export const sessions = {
  list: () => get<SessionsResponse>("/android/sessions"),
  revoke: (id: number) => del<{ status: string }>(`/android/sessions/${id}`),
  revokeAll: () => post<{ status: string }>("/android/sessions/revoke-all"),
};

// ---------------------------------------------------------------------------
// Payments (web-specific, discount-aware)
// ---------------------------------------------------------------------------

export interface WebMenuInvoice {
  provider: string;
  amount: number;
  original_amount: number;
  currency: string;
  method: string | null;
  days: number;
  tariff_slug: string;
}

export interface WebMenuNode {
  id: number;
  parent_id: number | null;
  text: string;
  action: string | null;
  invoice: WebMenuInvoice | null;
  children: WebMenuNode[];
}

export interface WebMenuResponse {
  tree: WebMenuNode[];
  discount_percent: number;
  promo_code: string | null;
}

export interface WebInvoiceResponse {
  provider: string;
  invoice_id: string;
  url: string;
  amount: number;
  original_amount: number;
  discount_percent: number;
  currency: string;
  transaction_id: string;
  payment_method: string;
}

export const webPayments = {
  getMenu: () => get<WebMenuResponse>("/web/payments/menu"),
  createInvoice: (node_id: number, description?: string) =>
    post<WebInvoiceResponse>("/web/payments/invoice", { node_id, description }),
};

// ---------------------------------------------------------------------------
// Transactions
// ---------------------------------------------------------------------------

export interface TransactionInfo {
  transaction_id: string;
  status: string;
  delivery_status: number;
  payment_method: string | null;
  amount: number | null;
  days_ordered: number;
  created_at: string | null;
}

export interface TransactionsResponse {
  transactions: TransactionInfo[];
}

export const transactions = {
  list: () => get<TransactionsResponse>("/android/payments/transactions"),
};

// ---------------------------------------------------------------------------
// Invite validation (unauthenticated)
// ---------------------------------------------------------------------------

export interface ValidateInviteResponse {
  valid: boolean;
  discount_percent: number | null;
  promo_type: string | null;
}

export const invite = {
  validate: (invite_code: string) =>
    post<ValidateInviteResponse>("/web/validate-invite", { invite_code }, false),
};

// ---------------------------------------------------------------------------
// Password
// ---------------------------------------------------------------------------

export const password = {
  change: (current_password: string, new_password: string) =>
    post<{ status: string }>("/android/auth/password/change", {
      current_password,
      new_password,
    }),
  resetRequest: (emailAddr: string) =>
    post<{ status: string }>(
      "/android/auth/password/reset-request",
      { email: emailAddr },
      false
    ),
};
