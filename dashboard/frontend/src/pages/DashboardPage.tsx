import { useEffect, useState } from "react";
import { Row, Col, Card, Table, Tag, Typography, Select, Space } from "antd";
import {
  UserOutlined,
  DollarOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import StatsCard from "../components/StatsCard";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import { api } from "../api/client";
import type { OverviewStats, TransactionItem } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

const statusColor: Record<string, string> = {
  created: "blue",
  confirmed: "green",
  delivered: "cyan",
  failed: "red",
  cancelled: "orange",
};

const periodOptions = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "6month", label: "6 Months" },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [recent, setRecent] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("month");
  const isMobile = useIsMobile();

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview"),
      api.get<TransactionItem[]>("/transactions/recent?limit=10"),
    ]).then(([s, r]) => {
      setStats(s);
      setRecent(r);
      setLoading(false);
    });
  }, []);

  const recentColumns = [
    { title: "ID", dataIndex: "transaction_id", key: "id", width: 140, ellipsis: true },
    { title: "User", dataIndex: "username", key: "user", width: 100 },
    { title: "Method", dataIndex: "payment_method", key: "method", width: 100 },
    { title: "Amount", dataIndex: "amount", key: "amount", width: 80, render: (v: number | null) => v ?? "\u2014" },
    {
      title: "Status",
      dataIndex: "order_status",
      key: "status",
      width: 100,
      render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag>,
    },
    { title: "Date", dataIndex: "created_at", key: "date", width: 160 },
  ];

  const renderRecentMobile = (tx: TransactionItem) => (
    <div
      key={tx.transaction_id}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {tx.username || "—"} · {tx.payment_method || "—"}
        </div>
        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
          {tx.created_at || "—"}
        </div>
      </div>
      <div style={{ textAlign: "right", marginLeft: 8 }}>
        <Tag color={statusColor[tx.order_status] || "default"} style={{ margin: 0 }}>
          {tx.amount != null ? tx.amount : "—"}
        </Tag>
      </div>
    </div>
  );

  return (
    <div>
      <div
        style={{
          marginBottom: isMobile ? 12 : 20,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: "rgba(255,255,255,0.88)" }}>
          Dashboard
        </Typography.Title>
        <Select
          value={period}
          onChange={setPeriod}
          style={{ width: 130 }}
          options={periodOptions}
        />
      </div>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Total Users"
            value={stats?.total_users ?? 0}
            prefix={<TeamOutlined />}
            loading={loading}
            color="#4f8cff"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Paid Users"
            value={stats?.paid_users ?? 0}
            prefix={<UserOutlined />}
            loading={loading}
            color="#36cfc9"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Free Users"
            value={stats?.free_users ?? 0}
            prefix={<UserOutlined />}
            loading={loading}
            color="#ffc53d"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Total Revenue"
            value={stats?.revenue ?? 0}
            prefix={<DollarOutlined />}
            loading={loading}
            color="#b37feb"
          />
        </Col>
      </Row>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: isMobile ? 8 : 16 }}>
        <Col xs={24} lg={16}>
          <RevenueChart period={period} />
        </Col>
        <Col xs={24} lg={8}>
          <PaymentMethodPieChart />
        </Col>
      </Row>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: isMobile ? 8 : 16 }}>
        <Col xs={24} lg={12}>
          <UserGrowthChart period={period} />
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Recent Transactions</span>}
          >
            {isMobile ? (
              recent.map(renderRecentMobile)
            ) : (
              <Table
                rowKey="transaction_id"
                columns={recentColumns}
                dataSource={recent}
                loading={loading}
                pagination={false}
                size="small"
                scroll={{ x: 600 }}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
