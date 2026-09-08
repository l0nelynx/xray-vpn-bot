export interface UserItem {
  id: number;
  tg_id: number | null;
  username: string | null;
  vless_uuid: string | null;
  rw_id: number | null;
  api_provider: string;
  is_banned: boolean;
  is_paid: boolean;
  vip: boolean;
  email: string | null;
  language: string | null;
  subscriptions_count: number;
}

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

export interface UserDetail extends UserItem {
  transactions_count: number;
  total_spent: number;
  promo_code: string | null;
  tickets_count: number;
  bonus_credits: number;
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
  purchase_source: "bot" | "miniapp" | "android" | "web" | "legacy_unknown";
  delivery_error: string | null;
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

export interface MetricDelta {
  value: number;
  prev: number;
}

export interface SummaryStats {
  period: string;
  revenue: MetricDelta;
  orders: MetricDelta;
  new_users: MetricDelta;
  avg_order: MetricDelta;
  totals: {
    total_users: number;
    active_subs: number;
    conversion: number;
    revenue_all_time: number;
  };
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

export interface ApiServiceHealth {
  service: "miniapp" | "bot" | "dashboard";
  is_healthy: boolean;
  checked_at: string;
  last_ok_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
  response_time_ms: number | null;
}

export interface ApiHealthSummary {
  requests: number;
  avg_rps: number;
  success_rate: number;
  client_errors: number;
  server_errors: number;
  error_rate: number;
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  client_error_rate: number;
  server_error_rate: number;
  slow_requests: number;
  dropped_events: number;
  last_telemetry_at: string | null;
  services: ApiServiceHealth[];
}

export interface ApiHealthSeriesPoint {
  bucket: string;
  requests: number;
  status_2xx: number;
  status_3xx: number;
  status_4xx: number;
  status_5xx: number;
  error_rate: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
}

export interface ApiEndpointHealth extends Omit<ApiHealthSummary, "avg_rps" | "last_telemetry_at" | "services"> {
  service: string;
  method: string;
  route: string;
  last_error_at: string | null;
}

export interface ApiErrorEvent {
  id: number;
  occurred_at: string;
  request_id: string;
  service: string;
  method: string;
  route: string;
  status_code: number;
  duration_ms: number;
  user_id: number | null;
  tg_id: number | null;
  actor: string | null;
  client_ip: string | null;
  client_channel: string | null;
  user_agent: string | null;
  app_version: string | null;
  exception_type: string | null;
  error_message: string | null;
  error_fingerprint: string;
  traceback?: string | null;
}

export interface ApiErrorGroup {
  fingerprint: string;
  service: string;
  route: string;
  status_code: number;
  exception_type: string | null;
  message: string | null;
  count: number;
  affected_users: number;
  last_seen_at: string;
}

export interface ApiAlertSettings {
  enabled: boolean;
  server_error_threshold: number;
  latency_p95_ms: number;
  latency_min_requests: number;
  health_failures: number;
  cooldown_minutes: number;
}

export interface PromoItem {
  promo_code: string;
  promo_type: string;
  owner_username: string | null;
  owner_tg_id: number;
  usage_count: number;
  days_purchased: number;
  points_rewarded: number;
  credit_grant: number | null;
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
  tls_domains?: string[];
}

export interface TelmtUser {
  username: string;
  enabled?: boolean;
  in_runtime: boolean;
  user_ad_tag: string | null;
  max_tcp_conns: number | null;
  expiration_rfc3339: string | null;
  data_quota_bytes: number | null;
  max_unique_ips: number | null;
  rate_limit_up_bps: number | null;
  rate_limit_down_bps: number | null;
  current_connections: number;
  active_unique_ips: number;
  active_unique_ips_list: string[];
  recent_unique_ips: number;
  recent_unique_ips_list: string[];
  total_octets: number;
  links: TelmtUserLink;
}

export interface TelmtUserQuota {
  username: string;
  data_quota_bytes: number;
  used_bytes: number;
  last_reset_epoch_secs: number | null;
}

export interface TelmtUsersQuotaResponse {
  users: TelmtUserQuota[];
}

export interface TelmtHealthReady {
  ready: boolean;
  status?: string;
  reason?: string;
  admission_open?: boolean;
  healthy_upstreams?: number;
  total_upstreams?: number;
}

export interface TelmtConnTopUser {
  username: string;
  current_connections: number;
  total_octets: number;
}

export interface TelmtRuntimeConnectionsSummary {
  enabled?: boolean;
  generated_at_epoch_secs?: number;
  reason?: string;
  data?: {
    totals?: {
      current_connections?: number;
      current_connections_me?: number;
      current_connections_direct?: number;
      active_users?: number;
    };
    top?: {
      limit?: number;
      by_connections?: TelmtConnTopUser[];
      by_throughput?: TelmtConnTopUser[];
    };
    telemetry?: {
      user_enabled?: boolean;
      throughput_is_cumulative?: boolean;
    };
  };
}

export interface TelmtRuntimeEvent {
  seq: number;
  ts_epoch_secs: number;
  event_type: string;
  context?: string;
}

export interface TelmtRuntimeRecentEvents {
  enabled?: boolean;
  generated_at_epoch_secs?: number;
  reason?: string;
  data?: {
    capacity?: number;
    dropped_total?: number;
    events?: TelmtRuntimeEvent[];
  };
  /** legacy/flat shape fallback */
  events?: TelmtRuntimeEvent[];
}

export interface TelmtTlsFingerprintRow {
  scope?: string;
  ja3?: string;
  ja4?: string;
  total?: number;
  auth_success?: number;
  bad_or_probe?: number;
  first_seen_epoch_secs?: number;
  last_seen_epoch_secs?: number;
}

export interface TelmtTlsFingerprints {
  enabled?: boolean;
  generated_at_epoch_secs?: number;
  reason?: string;
  data?: {
    limit?: number;
    retention_secs?: number;
    capacity?: number;
    dropped_total?: number;
    parse_error_total?: number;
    by_fingerprint?: TelmtTlsFingerprintRow[];
    by_ip?: TelmtTlsFingerprintRow[];
    by_cidr?: TelmtTlsFingerprintRow[];
    by_user?: TelmtTlsFingerprintRow[];
  };
}

export interface TelmtLimitsEffective {
  update_every_secs?: number;
  me_reinit_every_secs?: number;
  me_pool_force_close_secs?: number;
  timeouts?: Record<string, number | boolean | string>;
  upstream?: Record<string, number | boolean | string>;
  middle_proxy?: Record<string, number | boolean | string>;
  user_ip_policy?: Record<string, number | boolean | string>;
  user_tcp_policy?: Record<string, number | boolean | string>;
}

export interface TelmtSecurityWhitelist {
  enabled?: boolean;
  entries_total?: number;
  entries?: string[];
  generated_at_epoch_secs?: number;
}

export interface TelmtFreeParams {
  max_tcp_conns: number | null;
  max_unique_ips: number | null;
  data_quota_bytes: number | null;
  expire_days: number;
  rate_limit_up_bps: number | null;
  rate_limit_down_bps: number | null;
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

export interface TelmtBulkError {
  username: string;
  status: number;
  detail: string;
}

export interface TelmtBulkResult {
  processed: number;
  succeeded: number;
  failed: number;
  errors: TelmtBulkError[];
}

/** Top-level sections Telemt exposes via GET/PATCH /v1/config. */
export const TELMT_EDITABLE_CONFIG_SECTIONS = [
  "general",
  "timeouts",
  "censorship",
  "upstreams",
  "dc_overrides",
  "server",
] as const;

export type TelmtConfigSectionName = (typeof TELMT_EDITABLE_CONFIG_SECTIONS)[number];

export interface TelmtServerConfigData {
  /** Replaced wholesale by PATCH. Other server fields are never exposed. */
  listeners?: Record<string, unknown>[];
}

/** Telemt managed-config JSON (subset of config.toml). */
export type TelmtConfigData = Partial<
  Record<Exclude<TelmtConfigSectionName, "server">, unknown>
> & {
  server?: TelmtServerConfigData;
};

export interface TelmtPatchConfigResponse {
  revision: string;
  restart_required: boolean;
  changed: string[];
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
  category?: string;
  context?: Record<string, unknown>;
  last_sender?: string;
  waiting_since?: string | null;
  unread?: boolean;
  last_message_id?: number;
  can_reopen?: boolean;
  assignee?: string | null;
  last_message_preview?: string;

  id: number;
  user_id: number;
  tg_id: number | null;
  username: string | null;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SupportAttachmentOut {
  id: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  url: string;
}

export interface SupportMessageItem {
  author?: string | null;
  id: number;
  sender: string;
  text: string;
  created_at: string;
  attachments: SupportAttachmentOut[];
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
