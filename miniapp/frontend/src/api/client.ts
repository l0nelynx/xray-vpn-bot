import { getInitData } from "../tg/webapp";

const BASE = "/bot/miniapp/api";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    "X-Telegram-Init-Data": getInitData(),
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export interface UserInfo {
  tg_id: number;
  username: string | null;
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
}

export interface LinksInfo {
  bot_url: string;
  policy_url: string;
  agreement_url: string;
}

export interface MeResponse {
  registered: boolean;
  user?: UserInfo;
  subscription?: SubscriptionInfo;
  links: LinksInfo;
}

export interface TicketSummary {
  id: number;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_message_preview: string;
}

export interface MessageItem {
  id: number;
  sender: string;
  text: string;
  created_at: string;
}

export interface TicketDetail {
  id: number;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
}

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

export type PaymentProviderName = "apay" | "crystal" | "crypto";

export interface ProviderInfo {
  name: PaymentProviderName;
  payment_method: string;
  currencies: string[];
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
}

export interface InvoiceCreateRequest {
  provider: PaymentProviderName;
  amount: number;
  currency: string;
  days: number;
  tariff_slug?: string;
  description?: string;
}

export interface InvoiceResponse {
  provider: PaymentProviderName;
  invoice_id: string;
  url: string;
  amount: number;
  currency: string;
  transaction_id: string;
  payment_method: string;
}

export const payments = {
  listProviders: () => api.get<ProvidersResponse>("/payments/providers"),
  createInvoice: (body: InvoiceCreateRequest) =>
    api.post<InvoiceResponse>("/payments/invoice", body),
};

export type MenuNodeAction = "buttons" | "invoice";

export interface MenuInvoice {
  provider: PaymentProviderName;
  amount: number;
  currency: string;
  days: number | null;
  tariff_slug: string | null;
}

export interface MenuNode {
  id: number;
  parent_id: number | null;
  text: string;
  action: MenuNodeAction;
  invoice: MenuInvoice | null;
  children: MenuNode[];
}

export interface MenuTreeResponse {
  tree: MenuNode[];
}

export const menu = {
  getTree: () => api.get<MenuTreeResponse>("/menu/tree"),
};
