import { useState, useEffect, useCallback } from "react";
import {
  Wallet,
  UserPlus,
  ShoppingCart,
  TrendingUp,
  Users2,
  Crown,
  Percent,
  DollarSign,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { toast } from "sonner";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import MetricCard from "../components/MetricCard";
import { api } from "../api/client";
import type { SummaryStats, OrderStatusStat } from "../api/types";
import { PERIOD_OPTIONS } from "../utils/constants";

const rub = (v: number) => Math.round(v).toLocaleString("en-US");

export default function StatsPage() {
  const [period, setPeriod] = useState("month");
  const [summary, setSummary] = useState<SummaryStats | null>(null);
  const [orderStatuses, setOrderStatuses] = useState<OrderStatusStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback((p: string) => {
    setLoading(true);
    setError(null);
    api
      .get<SummaryStats>(`/stats/summary?period=${p}`)
      .then((data) => {
        setSummary(data);
        setError(null);
      })
      .catch(() => {
        setSummary(null);
        setError("Failed to load statistics");
        toast.error("Failed to load statistics");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadSummary(period);
  }, [period, loadSummary]);

  useEffect(() => {
    api
      .get<OrderStatusStat[]>("/stats/order-statuses")
      .then(setOrderStatuses)
      .catch(() => {});
  }, []);

  const totalOrders = orderStatuses.reduce((acc, s) => acc + s.count, 0);
  const maxStatus = Math.max(...orderStatuses.map((s) => s.count), 1);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Statistics</h2>
          <p className="text-sm text-muted-foreground">
            Deeper breakdown of revenue, growth and order health.
          </p>
        </div>
        <Select value={period} onValueChange={(v: string) => setPeriod(v)}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PERIOD_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {error && (
        <Alert variant="destructive" className="flex items-center justify-between gap-3">
          <AlertDescription>{error}</AlertDescription>
          <Button size="sm" variant="outline" onClick={() => loadSummary(period)}>
            Retry
          </Button>
        </Alert>
      )}

      {!error && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard
            label="Revenue"
            value={summary?.revenue.value ?? 0}
            prev={summary?.revenue.prev}
            icon={<Wallet />}
            format={rub}
            suffix="₽"
            loading={loading}
          />
          <MetricCard
            label="New Users"
            value={summary?.new_users.value ?? 0}
            prev={summary?.new_users.prev}
            icon={<UserPlus />}
            loading={loading}
          />
          <MetricCard
            label="Orders"
            value={summary?.orders.value ?? 0}
            prev={summary?.orders.prev}
            icon={<ShoppingCart />}
            loading={loading}
          />
          <MetricCard
            label="Avg Order"
            value={summary?.avg_order.value ?? 0}
            prev={summary?.avg_order.prev}
            icon={<TrendingUp />}
            format={rub}
            suffix="₽"
            loading={loading}
          />
        </div>
      )}

      {!error && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard
            label="Total Users"
            value={summary?.totals.total_users ?? 0}
            icon={<Users2 />}
            loading={loading}
          />
          <MetricCard
            label="Active Subs"
            value={summary?.totals.active_subs ?? 0}
            icon={<Crown />}
            loading={loading}
          />
          <MetricCard
            label="Conversion"
            value={summary?.totals.conversion ?? 0}
            icon={<Percent />}
            format={(v) => v.toFixed(1)}
            suffix="%"
            loading={loading}
          />
          <MetricCard
            label="Lifetime Revenue"
            value={summary?.totals.revenue_all_time ?? 0}
            icon={<DollarSign />}
            format={rub}
            suffix="₽"
            loading={loading}
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RevenueChart period={period} />
        </div>
        <div>
          <PaymentMethodPieChart />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <UserGrowthChart period={period} />
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Order Statuses</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              {orderStatuses.length === 0 && (
                <div className="py-5 text-center text-muted-foreground">No data for this period</div>
              )}
              {orderStatuses.map((s) => {
                const pct = totalOrders ? (s.count / totalOrders) * 100 : 0;
                const barPct = (s.count / maxStatus) * 100;
                return (
                  <div key={s.status}>
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-sm capitalize text-muted-foreground">{s.status}</span>
                      <span className="text-sm">
                        <span className="font-semibold">{s.count.toLocaleString("en-US")}</span>
                        <span className="ml-1.5 text-xs text-muted-foreground">
                          {pct.toFixed(0)}%
                        </span>
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-md bg-muted">
                      <div
                        className="h-full rounded-md bg-primary transition-all"
                        style={{ width: `${barPct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              {totalOrders > 0 && (
                <div className="mt-1 flex justify-between border-t pt-3 text-xs text-muted-foreground">
                  <span>Total orders</span>
                  <span className="font-semibold text-foreground">
                    {totalOrders.toLocaleString("en-US")}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
