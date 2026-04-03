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
