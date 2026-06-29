import { useEffect, useState } from "react";
import { Row, Col, Card, Table, Tag, Select, App } from "antd";
import {
  UserOutlined,
  DollarOutlined,
  TeamOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import StatsCard from "../components/StatsCard";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import { api } from "../api/client";
import type { OverviewStats, TransactionItem } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import { STATUS_COLORS, PERIOD_OPTIONS } from "../utils/constants";

export default function DashboardPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [recent, setRecent] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("month");
  const isMobile = useIsMobile();
  const { message } = App.useApp();

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview"),
      api.get<TransactionItem[]>("/transactions/recent?limit=10"),
    ])
      .then(([s, r]) => {
        setStats(s);
        setRecent(r);
      })
      .catch(() => {
        message.error("Failed to load dashboard data");
      })
      .finally(() => {
        setLoading(false);
      });
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

      {/* KPI cards */}
      <Row gutter={[gap, gap]}>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Total Users"
            value={stats?.total_users ?? 0}
            prefix={<TeamOutlined />}
            loading={loading}
            color="#6C8EFF"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Paid Users"
            value={stats?.paid_users ?? 0}
            prefix={<UserOutlined />}
            loading={loading}
            color="#34D399"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Free Users"
            value={stats?.free_users ?? 0}
            prefix={<UserOutlined />}
            loading={loading}
            color="#FBBF24"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Revenue"
            value={stats?.revenue ?? 0}
            prefix={<DollarOutlined />}
            loading={loading}
            color="#A78BFF"
          />
        </Col>
      </Row>

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

      {/* Avg order stat — footer row */}
      {stats && (
        <div
          style={{
            marginTop: gap,
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "10px 14px",
            background: "#111827",
            border: "1px solid #1E2540",
            borderRadius: 10,
          }}
        >
          <RiseOutlined style={{ color: "#A78BFF", fontSize: 14 }} />
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.40)" }}>
            Average order value:
          </span>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#E2E8F8" }}>
            {Math.round(stats.avg_order).toLocaleString("en-US")}
          </span>
        </div>
      )}
    </div>
  );
}
