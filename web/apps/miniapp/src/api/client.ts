import { createJsonClient } from "@xray/api";

import { getInitData } from "../tg/webapp";

const BASE = "/bot/miniapp/api";

export { ApiError } from "@xray/api";

export const api = createJsonClient({
  base: BASE,
  getHeaders: () => ({ "X-Telegram-Init-Data": getInitData() }),
});

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
  news_url: string;
  branding_name: string;
  support_bot_link: string;
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

export type PaymentProviderName = "apay" | "crystal" | "crypto" | "platega";

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
  method?: string;
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
  method: string | null;
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
  can_activate: boolean;
  active_promo: string | null;
  discount_percent: number;
  default_discount_percent: number;
}

export interface PromoActivateResponse {
  ok: boolean;
  active_promo: string;
  discount_percent: number;
}

export const promo = {
  getState: () => api.get<PromoState>("/promo"),
  activate: (promo_code: string) =>
    api.post<PromoActivateResponse>("/promo", { promo_code }),
};

export interface ReferralState {
  code: string;
  deeplink: string;
  discount_percent: number;
  days_reward_per_30: number;
  reward_cap_days: number;
  days_purchased: number;
  days_rewarded: number;
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
