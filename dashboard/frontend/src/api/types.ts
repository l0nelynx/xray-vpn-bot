export interface UserItem {
  id: number;
  tg_id: number;
  username: string | null;
  api_provider: string;
  is_banned: boolean;
  is_paid: boolean;
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
