export interface SegmentParamOption {
  value: string;
  label: string;
}

export interface SegmentParam {
  name: string;
  label: string;
  type: "int" | "float" | "select";
  default: number | string;
  min?: number;
  max?: number;
  options?: SegmentParamOption[];
}

export type SegmentParams = Record<string, number | string>;

export interface SegmentDef {
  id: string;
  title: string;
  description: string;
  params: SegmentParam[];
}

export interface ConditionTypeMeta {
  type: string;
  label: string;
  category?: "base" | "remnawave";
  description: string;
  required?: boolean;
  fields?: Array<Record<string, unknown>>;
}

export interface ActionTypeMeta {
  type: string;
  label: string;
  category: "telegram" | "remnawave";
  available?: boolean;
  fields?: Array<Record<string, unknown>>;
}

export interface CrmCondition {
  type: string;
  segment_id?: string;
  params?: SegmentParams;
  value?: string;
  tg_ids?: number[];
  squad_id?: string;
  limit_gb?: number;
  tag?: string;
}

export interface InternalSquadOption {
  uuid: string;
  name: string;
}

export interface CrmAction {
  type: string;
  enabled: boolean;
  order?: number;
  text?: string;
  button_type?: string;
  days?: number;
  gb?: number;
  status?: string;
}

export interface ScanUser {
  tg_id: number;
  username: string | null;
  vless_uuid: string | null;
  meta: Record<string, unknown>;
}

export interface ScanResult {
  segment_id: string;
  total: number;
  users: ScanUser[];
  warning: string | null;
}

export interface CampaignSummary {
  id: number;
  name: string;
  segment_type: string | null;
  status: string;
  total_targets: number;
  messages_sent: number;
  messages_failed: number;
  perks_applied: number;
  perks_failed: number;
  bonus_days: number | null;
  bonus_traffic_gb: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_by: string;
}

export interface CrmEventRow {
  id: number;
  name: string;
  enabled: boolean;
  segment_type: string | null;
  segment_params: SegmentParams;
  conditions: CrmCondition[];
  actions: CrmAction[];
  run_at_time: string;
  frequency: string;
  weekday: number | null;
  message_text: string;
  attach_button: boolean;
  bonus_days: number | null;
  bonus_traffic_gb: number | null;
  repeat_policy: string;
  repeat_cooldown_days: number;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface WebhookEventOption {
  value: string;
  label: string;
}

export interface WebhookScopeGroup {
  scope: string;
  label: string;
  events: WebhookEventOption[];
}

export interface CrmWebhookRuleRow {
  id: number;
  name: string;
  enabled: boolean;
  scope: string;
  event: string;
  actions: CrmAction[];
  cooldown_hours: number | null;
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface MessageTemplate {
  id: string;
  segment_id: string;
  title: string;
  message_text: string;
  suggested_bonus_days: number | null;
  suggested_bonus_traffic_gb: number | null;
  attach_button: boolean;
}

export interface CrmVariable {
  key: string;
  label: string;
  description: string;
  example: string;
}

export const USER_TYPE_OPTIONS = [
  { value: "all", label: "All" },
  { value: "free", label: "Free" },
  { value: "paid_vip", label: "Paid / VIP" },
];

export const WEEKDAYS = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

export const REPEAT_POLICIES = [
  { value: "always", label: "Always" },
  { value: "once", label: "Once" },
  { value: "cooldown", label: "Cooldown" },
];
