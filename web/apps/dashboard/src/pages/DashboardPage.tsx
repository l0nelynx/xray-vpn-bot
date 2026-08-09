import { useEffect, useState, useCallback } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { UserPlus, Wallet, ShoppingCart, TrendingUp } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { toast } from "sonner";
import MetricCard from "../components/MetricCard";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import DataTable from "../components/DataTable";
import { api } from "../api/client";
import type { SummaryStats, TransactionItem } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import { PERIOD_OPTIONS, statusBadgeVariant } from "../utils/constants";
import ApiHealthWidget from "../components/ApiHealthWidget";

const rub = (v: number) => Math.round(v).toLocaleString("en-US");

export default function DashboardPage() {
  const [summary, setSummary] = useState<SummaryStats | null>(null);
  const [recent, setRecent] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [period, setPeriod] = useState("month");
  const isMobile = useIsMobile();

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
        setError("Failed to load dashboard data");
        toast.error("Failed to load dashboard data");
      })
      .finally(() => setLoading(false));
  }, []);

  const loadRecent = useCallback(() => {
    setRecentLoading(true);
    setRecentError(null);
    api
      .get<TransactionItem[]>("/transactions/recent?limit=10")
      .then((data) => {
        setRecent(data);
        setRecentError(null);
      })
      .catch(() => {
        setRecent([]);
        setRecentError("Failed to load recent transactions");
      })
      .finally(() => setRecentLoading(false));
  }, []);

  useEffect(() => {
    loadSummary(period);
  }, [period, loadSummary]);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

  const recentColumns: ColumnDef<TransactionItem, unknown>[] = [
    {
      id: "transaction_id",
      header: "ID",
      meta: { width: 140 },
      cell: ({ row }) => (
        <span className="block max-w-[140px] truncate font-mono text-xs text-muted-foreground">
          {row.original.transaction_id}
        </span>
      ),
    },
    {
      id: "username",
      header: "User",
      meta: { width: 110 },
      cell: ({ row }) => <span className="text-foreground/75">{row.original.username || "—"}</span>,
    },
    {
      id: "payment_method",
      header: "Method",
      meta: { width: 110 },
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{row.original.payment_method || "—"}</span>
      ),
    },
    {
      id: "amount",
      header: "Amount",
      meta: { width: 90 },
      cell: ({ row }) => (
        <span className="font-semibold">{row.original.amount ?? "—"}</span>
      ),
    },
    {
      id: "order_status",
      header: "Status",
      meta: { width: 110 },
      cell: ({ row }) => (
        <Badge variant={statusBadgeVariant(row.original.order_status)}>
          {row.original.order_status}
        </Badge>
      ),
    },
    {
      id: "created_at",
      header: "Date",
      meta: { width: 155 },
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{row.original.created_at || "—"}</span>
      ),
    },
  ];

  const renderRecentMobile = (tx: TransactionItem) => (
    <div
      key={tx.transaction_id}
      className="flex items-center justify-between border-b border-border py-2.5 last:border-0"
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-foreground/75">
          {tx.username || "—"} · {tx.payment_method || "—"}
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">{tx.created_at || "—"}</div>
      </div>
      <div className="ml-2 text-right">
        <Badge variant={statusBadgeVariant(tx.order_status)}>
          {tx.amount != null ? tx.amount : "—"}
        </Badge>
      </div>
    </div>
  );

  const totals = summary
    ? [
        { label: "Total users", value: summary.totals.total_users.toLocaleString("en-US") },
        { label: "Active subs", value: summary.totals.active_subs.toLocaleString("en-US") },
        { label: "Conversion", value: `${summary.totals.conversion.toFixed(1)}%` },
        { label: "Lifetime revenue", value: `${rub(summary.totals.revenue_all_time)} ₽` },
      ]
    : [];

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1.5">
          <h2 className="text-2xl font-semibold tracking-tight">Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            Overview of revenue, users and orders for the selected period.
          </p>
        </div>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-[160px]">
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
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

      {summary && !error && (
        <Card>
          <CardContent className="grid grid-cols-2 gap-6 pt-6 sm:grid-cols-4">
            {totals.map((it) => (
              <div key={it.label} className="space-y-1.5">
                <p className="text-sm text-muted-foreground">{it.label}</p>
                <p className="text-lg font-semibold tracking-tight">{it.value}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <ApiHealthWidget />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RevenueChart period={period} />
        </div>
        <div>
          <PaymentMethodPieChart />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <UserGrowthChart period={period} />
        <Card>
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
            <CardDescription>Latest 10 orders across all payment methods.</CardDescription>
          </CardHeader>
          <CardContent>
            {recentError ? (
              <Alert variant="destructive" className="flex items-center justify-between gap-3">
                <AlertDescription>{recentError}</AlertDescription>
                <Button size="sm" variant="outline" onClick={loadRecent}>
                  Retry
                </Button>
              </Alert>
            ) : isMobile ? (
              recentLoading ? (
                <div className="py-8 text-center text-muted-foreground">Loading…</div>
              ) : recent.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  No recent transactions
                </div>
              ) : (
                <div>{recent.map(renderRecentMobile)}</div>
              )
            ) : (
              <DataTable
                columns={recentColumns}
                data={recent}
                loading={recentLoading}
                rowKey={(r) => r.transaction_id}
                empty="No recent transactions"
                minWidth={620}
                embedded
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
