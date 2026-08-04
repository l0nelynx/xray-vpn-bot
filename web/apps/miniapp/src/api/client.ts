import { ApiError, createJsonClient } from "@xray/api";

import { getInitData } from "../tg/webapp";

const BASE = "/bot/miniapp/api";

export { ApiError };

export const api = createJsonClient({
  base: BASE,
  getHeaders: () => ({ "X-Telegram-Init-Data": getInitData() }),
});

export interface UserInfo {
  tg_id: number;
  username: string | null;
  language: string | null;
  has_email?: boolean;
}

export interface SubscriptionInfo {
  subscription_id: number | null;
  label: string | null;
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
  news_url: string;
  branding_name: string;
  support_bot_link: string;
}

export interface MeResponse {
  registered: boolean;
  user?: UserInfo;
  subscription?: SubscriptionInfo;
  subscriptions_count: number;
  links: LinksInfo;
}

export type UiLanguage = "ru" | "en";

export const me = {
  setLanguage: (language: UiLanguage) =>
    api.patch<UserInfo>("/me/language", { language }),
};

export interface LinkEmailResponse {
  result: string;
  survivor_id: number;
}

export const linkEmail = {
  link: (email: string, password: string) =>
    api.post<LinkEmailResponse>("/link/email", { email, password }),
};

export interface TicketSummary {
  id: number;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_message_preview: string;
}

export interface AttachmentOut {
  id: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  url: string;
}

export interface MessageItem {
  id: number;
  sender: string;
  text: string;
  created_at: string;
  attachments: AttachmentOut[];
}

export interface TicketDetail {
  id: number;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
}

export const support = {
  addMessage: (ticketId: number, text: string, images: File[]) => {
    const form = new FormData();
    form.append("text", text);
    for (const img of images) form.append("images", img);
    return api.postForm<MessageItem>(`/support/tickets/${ticketId}/messages`, form);
  },
};

/** Fetches an attachment as a blob with the same auth header as `api` —
 * a plain <img src> can't carry X-Telegram-Init-Data, so callers build an
 * object URL from this instead (see useAuthedImage). */
export async function fetchAuthedBlob(url: string): Promise<Blob> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "X-Telegram-Init-Data": getInitData() },
  });
  if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  return res.blob();
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

export type PaymentProviderName = "apay" | "crystal" | "crypto" | "platega" | "paritypay";

export interface ProviderInfo {
  name: PaymentProviderName;
  payment_method: string;
  currencies: string[];
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
}

export interface InvoiceCreateRequest {
  node_id: number;
  description?: string;
  subscription_id?: number;
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
  getBalance: () => api.get<{ balance: number }>("/payments/balance"),
  createInvoice: (body: InvoiceCreateRequest) =>
    api.post<InvoiceResponse>("/payments/invoice", body),
  payWithCredits: (body: { node_id: number; subscription_id?: number }) =>
    api.post<PayCreditsResponse>("/payments/pay-credits", body),
};

export interface ManagedSubscription {
  id: number;
  rw_id: number;
  label: string | null;
  product_key: string | null;
  source: string;
  is_primary: boolean;
  tariff: string;
  status: string | null;
  days_left: number;
  expire_iso: string | null;
  data_limit_gb: number | null;
  traffic_used_gb: number;
  devices_count: number;
  subscription_url: string | null;
}

export const subscriptions = {
  list: () => api.get<{ subscriptions: ManagedSubscription[] }>("/subscriptions"),
  makePrimary: (subscriptionId: number) =>
    api.post<{ status: string; subscription_id: number }>(
      `/subscriptions/${subscriptionId}/primary`,
    ),
};

export type MenuNodeAction = "buttons" | "invoice";

export interface MenuInvoice {
  provider: PaymentProviderName;
  amount: number;
  currency: string;
  days: number | null;
  tariff_slug: string | null;
  method: string | null;
  points_cost?: number;
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

export interface PromoState {
  balance: number;
  last_promo_code: string | null;
  default_credit_grant: number;
}

export interface PromoActivateResponse {
  ok: boolean;
  promo_code: string;
  credit_grant: number;
  balance: number;
}

export interface PayCreditsResponse {
  ok: boolean;
  transaction_id?: string;
  points_spent?: number;
  points_cost?: number;
  credits_spent?: number;
  balance_after?: number;
  subscription_url?: string | null;
  message?: string | null;
}

export const promo = {
  getState: () => api.get<PromoState>("/promo"),
  activate: (promo_code: string) =>
    api.post<PromoActivateResponse>("/promo", { promo_code }),
};

export interface ReferralState {
  code: string;
  deeplink: string;
  credit_grant: number;
  points_reward_per_30: number;
  reward_cap_points: number;
  days_purchased: number;
  points_rewarded: number;
}

export const referral = {
  getState: () => api.get<ReferralState>("/promo/referral"),
};

export interface FreeCheckResponse {
  subscribed: boolean;
  news_url: string;
}

export interface FreeClaimResponse {
  ok: boolean;
  subscription_url: string | null;
  days: number | null;
  detail: string | null;
}

export interface TelemtClaimResponse {
  ok: boolean;
  link: string | null;
  detail: string | null;
}

export interface FreeStatusResponse {
  has_access: boolean;
  url: string | null;
  news_url: string;
}

export const free = {
  check: () => api.get<FreeCheckResponse>("/free/check"),
  claimVpn: () => api.post<FreeClaimResponse>("/free/claim"),
  claimTelemt: () => api.post<TelemtClaimResponse>("/free/telemt"),
  vpnStatus: () => api.get<FreeStatusResponse>("/free/vpn/status"),
  telemtStatus: () => api.get<FreeStatusResponse>("/free/telemt/status"),
};

// --- Connect page (app catalog) ------------------------------------------
// Mirrors the Remnawave subscription-page app-config.json schema. Localized
// strings are objects keyed by locale (en/ru/zh/fa/fr). Button links carry the
// {{SUBSCRIPTION_LINK}} / {{USERNAME}} placeholders substituted on the client.

export type LocalizedText = Record<string, string>;

export type ConnectButtonType = "external" | "subscriptionLink" | "copyButton";

export interface ConnectButton {
  link: string;
  text: LocalizedText;
  type: ConnectButtonType;
  svgIconKey?: string;
}

export interface ConnectBlock {
  title: LocalizedText;
  description?: LocalizedText;
  buttons: ConnectButton[];
  svgIconKey?: string;
  svgIconColor?: string;
}

export interface ConnectApp {
  name: string;
  blocks: ConnectBlock[];
  featured?: boolean;
  svgIconKey?: string;
}

export interface ConnectPlatform {
  apps: ConnectApp[];
}

export interface AppConfig {
  locales: string[];
  version: string;
  uiConfig?: {
    subscriptionInfoBlockType?: string;
    installationGuidesBlockType?: string;
  };
  platforms: Record<string, ConnectPlatform>;
  // svgIconKey -> raw SVG markup (brand logos + UI glyphs).
  svgLibrary?: Record<string, string>;
}

export const connect = {
  getAppConfig: () => api.get<AppConfig>("/connect/app-config"),
};
