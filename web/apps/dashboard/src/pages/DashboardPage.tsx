import { useEffect, useState, useCallback } from "react";
import { Row, Col, Card, Table, Tag, Select, App } from "antd";
import {
  UserAddOutlined,
  WalletOutlined,
  ShoppingOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import MetricCard from "../components/MetricCard";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import { api } from "../api/client";
import type { SummaryStats, TransactionItem } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import { STATUS_COLORS, PERIOD_OPTIONS } from "../utils/constants";

const rub = (v: number) => Math.round(v).toLocaleString("en-US");

export default function DashboardPage() {
  const [summary, setSummary] = useState<SummaryStats | null>(null);
  const [recent, setRecent] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("month");
  const isMobile = useIsMobile();
  const { message } = App.useApp();

  const loadSummary = useCallback(
    (p: string) => {
      setLoading(true);
      api
        .get<SummaryStats>(`/stats/summary?period=${p}`)
        .then(setSummary)
        .catch(() => message.error("Failed to load dashboard data"))
        .finally(() => setLoading(false));
    },
    [message]
  );

  useEffect(() => {
    loadSummary(period);
  }, [period, loadSummary]);

  useEffect(() => {
    api
      .get<TransactionItem[]>("/transactions/recent?limit=10")
      .then(setRecent)
      .catch(() => {});
  }, []);

  const recentColumns = [
    {
      title: "ID",
      dataIndex: "transaction_id",
      key: "id",
      width: 140,
      ellipsis: true,
      render: (v: string) => (
        <span style={{ fontFamily: "monospace", fontSize: 12, color: "rgba(255,255,255,0.45)" }}>
          {v}
        </span>
      ),
    },
    {
      title: "User",
      dataIndex: "username",
      key: "user",
      width: 110,
      render: (v: string) => (
        <span style={{ color: "rgba(255,255,255,0.75)" }}>{v || "—"}</span>
      ),
    },
    {
      title: "Method",
      dataIndex: "payment_method",
      key: "method",
      width: 110,
      render: (v: string) => (
        <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}>{v || "—"}</span>
      ),
    },
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      width: 90,
      render: (v: number | null) => (
        <span style={{ fontWeight: 600, color: "#E2E8F8" }}>{v ?? "—"}</span>
      ),
    },
    {
      title: "Status",
      dataIndex: "order_status",
      key: "status",
      width: 110,
      render: (s: string) => <Tag color={STATUS_COLORS[s] || "default"}>{s}</Tag>,
    },
    {
      title: "Date",
      dataIndex: "created_at",
      key: "date",
      width: 155,
      render: (v: string) => (
        <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>{v || "—"}</span>
      ),
    },
  ];

  const renderRecentMobile = (tx: TransactionItem) => (
    <div
      key={tx.transaction_id}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid #14192C",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            color: "rgba(255,255,255,0.75)",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {tx.username || "—"} · {tx.payment_method || "—"}
        </div>
        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.30)", marginTop: 2 }}>
          {tx.created_at || "—"}
        </div>
      </div>
      <div style={{ textAlign: "right", marginLeft: 8 }}>
        <Tag color={STATUS_COLORS[tx.order_status] || "default"} style={{ margin: 0 }}>
          {tx.amount != null ? tx.amount : "—"}
        </Tag>
      </div>
    </div>
  );

  const gap = isMobile ? 10 : 14;

  return (
    <div>
      {/* Period selector row */}
      <div
        style={{
          marginBottom: gap + 4,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.25)", letterSpacing: "0.6px", textTransform: "uppercase" }}>
          Overview
        </div>
        <Select
          value={period}
          onChange={setPeriod}
          style={{ width: 120 }}
          options={PERIOD_OPTIONS}
          size="small"
        />
      </div>

      {/* Period KPIs with deltas */}
      <Row gutter={[gap, gap]}>
        <Col xs={12} sm={12} lg={6}>
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
        <Col xs={12} sm={12} lg={6}>
          <MetricCard
            label="New Users"
            value={summary?.new_users.value ?? 0}
            prev={summary?.new_users.prev}
            icon={<UserAddOutlined />}
            color="#34D399"
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <MetricCard
            label="Orders"
            value={summary?.orders.value ?? 0}
            prev={summary?.orders.prev}
            icon={<ShoppingOutlined />}
            color="#6C8EFF"
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
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

      {/* All-time context strip */}
      {summary && (
        <div
          style={{
            marginTop: gap,
            display: "flex",
            flexWrap: "wrap",
            gap: isMobile ? 10 : 24,
            padding: isMobile ? "10px 14px" : "12px 18px",
            background: "#111827",
            border: "1px solid #1E2540",
            borderRadius: 12,
          }}
        >
          {[
            { label: "Total users", value: summary.totals.total_users.toLocaleString("en-US") },
            { label: "Active subs", value: summary.totals.active_subs.toLocaleString("en-US") },
            { label: "Conversion", value: `${summary.totals.conversion.toFixed(1)}%` },
            { label: "Lifetime revenue", value: `${rub(summary.totals.revenue_all_time)} ₽` },
          ].map((it) => (
            <div key={it.label} style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                {it.label}
              </span>
              <span style={{ fontSize: 14, fontWeight: 700, color: "#E2E8F8" }}>{it.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Charts row */}
      <Row gutter={[gap, gap]} style={{ marginTop: gap }}>
        <Col xs={24} lg={16}>
          <RevenueChart period={period} />
        </Col>
        <Col xs={24} lg={8}>
          <PaymentMethodPieChart />
        </Col>
      </Row>

      {/* Growth + Recent transactions */}
      <Row gutter={[gap, gap]} style={{ marginTop: gap }}>
        <Col xs={24} lg={12}>
          <UserGrowthChart period={period} />
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={
              <span style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.75)" }}>
                Recent Transactions
              </span>
            }
            styles={{ body: { padding: isMobile ? "12px 14px" : "0" } }}
          >
            {isMobile ? (
              <div style={{ padding: "2px 0" }}>{recent.map(renderRecentMobile)}</div>
            ) : (
              <Table
                rowKey="transaction_id"
                columns={recentColumns}
                dataSource={recent}
                loading={loading}
                pagination={false}
                size="small"
                scroll={{ x: 620 }}
                style={{ borderRadius: 0 }}
              />
            )}
          </Card>
        </Col>
      </Row>

    </div>
  );
}
