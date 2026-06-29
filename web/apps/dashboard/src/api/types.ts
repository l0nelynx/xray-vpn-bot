export interface UserItem {
  id: number;
  tg_id: number;
  username: string | null;
  api_provider: string;
  is_banned: boolean;
  is_paid: boolean;
  vip: boolean;
  email: string | null;
  language: string | null;
}

export interface UserDetail extends UserItem {
  vless_uuid: string | null;
  transactions_count: number;
  total_spent: number;
}

export interface TransactionItem {
  transaction_id: string;
  username: string;
  user_tg_id?: number;
  payment_method: string | null;
  amount: number | null;
  order_status: string;
  delivery_status: number;
  days_ordered: number;
  created_at: string | null;
  expire_date: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface OverviewStats {
  total_users: number;
  paid_users: number;
  free_users: number;
  revenue: number;
  avg_order: number;
}

export interface RevenuePoint {
  date: string;
  revenue: number;
}

export interface GrowthPoint {
  date: string;
  count: number;
}

export interface PaymentMethodStat {
  method: string;
  count: number;
  total: number;
}

export interface OrderStatusStat {
  status: string;
  count: number;
}

export interface PromoItem {
  promo_code: string;
  owner_username: string | null;
  owner_tg_id: number;
  usage_count: number;
  days_purchased: number;
  days_rewarded: number;
}

export interface TariffPrice {
  id?: number;
  payment_method: string;
  price: number;
  currency: string;
  is_active: boolean;
}

export interface TariffPlan {
  id: number;
  slug: string;
  name_ru: string;
  name_en: string;
  days: number;
  sort_order: number;
  is_active: boolean;
  discount_percent: number;
  created_at: string | null;
  squad_profile_id: number | null;
  prices: TariffPrice[];
}

export interface SquadProfile {
  id: number;
  name: string;
  squad_id: string;
  external_squad_id: string;
}

export interface MenuButton {
  id: number;
  screen_id: number;
  text_ru: string;
  text_en: string;
  callback_data: string | null;
  url: string | null;
  row: number;
  col: number;
  sort_order: number;
  button_type: string;
  is_active: boolean;
  visibility_condition: string;
}

// Telemt types
export interface TelmtEnvelope<T> {
  ok: boolean;
  data: T;
  revision: string;
}

export interface TelmtSystemInfo {
  version: string;
  target_arch: string;
  target_os: string;
  build_profile: string;
  git_commit?: string;
  build_time_utc?: string;
  rustc_version?: string;
  process_started_at_epoch_secs: number;
  uptime_seconds: number;
  config_path: string;
  config_hash: string;
  config_reload_count: number;
  last_config_reload_epoch_secs?: number;
}

export interface TelmtSummary {
  uptime_seconds: number;
  connections_total: number;
  connections_bad_total: number;
  handshake_timeouts_total: number;
  configured_users: number;
}

export interface TelmtHealth {
  status: string;
  read_only: boolean;
}

export interface TelmtRuntimeGates {
  accepting_new_connections: boolean;
  conditional_cast_enabled: boolean;
  me_runtime_ready: boolean;
  me2dc_fallback_enabled: boolean;
  use_middle_proxy: boolean;
  startup_status: string;
  startup_stage: string;
  startup_progress_pct: number;
}

export interface TelmtUserLink {
  classic: string[];
  secure: string[];
  tls: string[];
}

export interface TelmtUser {
  username: string;
  in_runtime: boolean;
  user_ad_tag: string | null;
  max_tcp_conns: number | null;
  expiration_rfc3339: string | null;
  data_quota_bytes: number | null;
  max_unique_ips: number | null;
  current_connections: number;
  active_unique_ips: number;
  active_unique_ips_list: string[];
  recent_unique_ips: number;
  recent_unique_ips_list: string[];
  total_octets: number;
  links: TelmtUserLink;
}

export interface TelmtFreeParams {
  max_tcp_conns: number | null;
  max_unique_ips: number | null;
  data_quota_bytes: number | null;
  expire_days: number;
}

export interface TelmtSecurityPosture {
  api_read_only: boolean;
  api_whitelist_enabled: boolean;
  api_whitelist_entries: number;
  api_auth_header_enabled: boolean;
  proxy_protocol_enabled: boolean;
  log_level: string;
  telemetry_core_enabled: boolean;
  telemetry_user_enabled: boolean;
  telemetry_me_level: string;
}

export interface OrderParam {
  id: number;
  item_id: number;
  param_id: number;
  user_data_id: number;
  type: string;
  data: string;
}

export interface SupportTicketSummary {
  id: number;
  user_id: number;
  tg_id: number | null;
  username: string | null;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SupportMessageItem {
  id: number;
  sender: string;
  text: string;
  created_at: string;
}

export interface SupportTicketDetail extends SupportTicketSummary {
  messages: SupportMessageItem[];
}

export interface MenuScreen {
  id: number;
  slug: string;
  name: string;
  message_text_ru: string | null;
  message_text_en: string | null;
  is_system: boolean;
  is_active: boolean;
  buttons: MenuButton[];
}
