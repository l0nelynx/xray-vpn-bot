import { useState, useEffect, useCallback } from "react";
import { Row, Col, Select, Typography, Card, App } from "antd";
import {
  WalletOutlined,
  UserAddOutlined,
  ShoppingOutlined,
  RiseOutlined,
  TeamOutlined,
  CrownOutlined,
  PercentageOutlined,
  DollarOutlined,
} from "@ant-design/icons";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import MetricCard from "../components/MetricCard";
import { api } from "../api/client";
import type { SummaryStats, OrderStatusStat } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import { PERIOD_OPTIONS } from "../utils/constants";

const rub = (v: number) => Math.round(v).toLocaleString("en-US");

const STATUS_HEX: Record<string, string> = {
  created: "#6C8EFF",
  confirmed: "#34D399",
  delivered: "#22D3EE",
  failed: "#F87171",
  cancelled: "#FBBF24",
};

export default function StatsPage() {
  const [period, setPeriod] = useState("month");
  const [summary, setSummary] = useState<SummaryStats | null>(null);
  const [orderStatuses, setOrderStatuses] = useState<OrderStatusStat[]>([]);
  const [loading, setLoading] = useState(true);
  const isMobile = useIsMobile();
  const { message } = App.useApp();

  const loadSummary = useCallback(
    (p: string) => {
      setLoading(true);
      api
        .get<SummaryStats>(`/stats/summary?period=${p}`)
        .then(setSummary)
        .catch(() => message.error("Failed to load statistics"))
        .finally(() => setLoading(false));
    },
    [message]
  );

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

  const gap = isMobile ? 10 : 16;

  return (
    <div>
      <div
        style={{
          marginBottom: gap,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: "rgba(255,255,255,0.88)" }}>
          Statistics
        </Typography.Title>
        <Select value={period} onChange={setPeriod} style={{ width: 140 }} options={PERIOD_OPTIONS} />
      </div>

      {/* Period KPIs with deltas vs previous period */}
      <Row gutter={[gap, gap]}>
        <Col xs={12} lg={6}>
          <MetricCard
            label="Revenue"
            value={summary?.revenue.value ?? 0}
            prev={summary?.revenue.prev}
            icon={<WalletOutlined />}
            color="#A78BFF"
            format={rub}
            suffix="₽"
            loading={loading}
          />
        </Col>
        <Col xs={12} lg={6}>
          <MetricCard
            label="New Users"
            value={summary?.new_users.value ?? 0}
            prev={summary?.new_users.prev}
            icon={<UserAddOutlined />}
            color="#34D399"
            loading={loading}
          />
        </Col>
        <Col xs={12} lg={6}>
          <MetricCard
            label="Orders"
            value={summary?.orders.value ?? 0}
            prev={summary?.orders.prev}
            icon={<ShoppingOutlined />}
            color="#6C8EFF"
            loading={loading}
          />
        </Col>
        <Col xs={12} lg={6}>
          <MetricCard
            label="Avg Order"
            value={summary?.avg_order.value ?? 0}
            prev={summary?.avg_order.prev}
            icon={<RiseOutlined />}
            color="#FBBF24"
            format={rub}
            suffix="₽"
            loading={loading}
          />
        </Col>
      </Row>

      {/* All-time context */}
      <Row gutter={[gap, gap]} style={{ marginTop: gap }}>
        <Col xs={12} lg={6}>
          <MetricCard label="Total Users" value={summary?.totals.total_users ?? 0} icon={<TeamOutlined />} color="#6C8EFF" loading={loading} />
        </Col>
        <Col xs={12} lg={6}>
          <MetricCard label="Active Subs" value={summary?.totals.active_subs ?? 0} icon={<CrownOutlined />} color="#34D399" loading={loading} />
        </Col>
        <Col xs={12} lg={6}>
          <MetricCard
            label="Conversion"
            value={summary?.totals.conversion ?? 0}
            icon={<PercentageOutlined />}
            color="#22D3EE"
            format={(v) => v.toFixed(1)}
            suffix="%"
            loading={loading}
          />
        </Col>
        <Col xs={12} lg={6}>
          <MetricCard
            label="Lifetime Revenue"
            value={summary?.totals.revenue_all_time ?? 0}
            icon={<DollarOutlined />}
            color="#A78BFF"
            format={rub}
            suffix="₽"
            loading={loading}
          />
        </Col>
      </Row>

      {/* Revenue + payment methods */}
      <Row gutter={[gap, gap]} style={{ marginTop: gap }}>
        <Col xs={24} lg={16}>
          <RevenueChart period={period} />
        </Col>
        <Col xs={24} lg={8}>
          <PaymentMethodPieChart />
        </Col>
      </Row>

      {/* Growth + order-status breakdown */}
      <Row gutter={[gap, gap]} style={{ marginTop: gap }}>
        <Col xs={24} lg={12}>
          <UserGrowthChart period={period} />
        </Col>
        <Col xs={24} lg={12}>
          <Card title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Order Statuses</span>}>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {orderStatuses.length === 0 && (
                <div style={{ color: "rgba(255,255,255,0.35)", textAlign: "center", padding: 20 }}>No data</div>
              )}
              {orderStatuses.map((s) => {
                const pct = totalOrders ? (s.count / totalOrders) * 100 : 0;
                const barPct = (s.count / maxStatus) * 100;
                const hex = STATUS_HEX[s.status] || "#6C8EFF";
                return (
                  <div key={s.status}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span style={{ fontSize: 13, color: "rgba(255,255,255,0.7)", textTransform: "capitalize" }}>
                        {s.status}
                      </span>
                      <span style={{ fontSize: 13 }}>
                        <span style={{ fontWeight: 700, color: "#E2E8F8" }}>{s.count.toLocaleString("en-US")}</span>
                        <span style={{ color: "rgba(255,255,255,0.35)", marginLeft: 6, fontSize: 12 }}>{pct.toFixed(0)}%</span>
                      </span>
                    </div>
                    <div style={{ height: 8, borderRadius: 6, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${barPct}%`,
                          height: "100%",
                          borderRadius: 6,
                          background: `linear-gradient(90deg, ${hex}99, ${hex})`,
                          transition: "width 0.4s ease",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
              {totalOrders > 0 && (
                <div
                  style={{
                    marginTop: 4,
                    paddingTop: 12,
                    borderTop: "1px solid rgba(255,255,255,0.06)",
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    color: "rgba(255,255,255,0.45)",
                  }}
                >
                  <span>Total orders</span>
                  <span style={{ color: "#E2E8F8", fontWeight: 600 }}>{totalOrders.toLocaleString("en-US")}</span>
                </div>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
