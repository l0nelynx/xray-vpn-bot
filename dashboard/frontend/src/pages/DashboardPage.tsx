import { useEffect, useState } from "react";
import { Row, Col, Card, Table, Tag } from "antd";
import {
  UserOutlined,
  DollarOutlined,
  TeamOutlined,
  ShoppingCartOutlined,
} from "@ant-design/icons";
import StatsCard from "../components/StatsCard";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import { api } from "../api/client";
import type { OverviewStats, TransactionItem } from "../api/types";

const statusColor: Record<string, string> = {
  created: "blue",
  confirmed: "green",
  delivered: "cyan",
  failed: "red",
  cancelled: "orange",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [recent, setRecent] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);

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
    { title: "Amount", dataIndex: "amount", key: "amount", width: 80, render: (v: number | null) => v ?? "—" },
    {
      title: "Status",
      dataIndex: "order_status",
      key: "status",
      width: 100,
      render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag>,
    },
    { title: "Date", dataIndex: "created_at", key: "date", width: 160 },
  ];

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <StatsCard
            title="Total Users"
            value={stats?.total_users ?? 0}
            prefix={<TeamOutlined />}
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatsCard
            title="Paid Users"
            value={stats?.paid_users ?? 0}
            prefix={<UserOutlined />}
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatsCard
            title="Free Users"
            value={stats?.free_users ?? 0}
            prefix={<UserOutlined />}
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatsCard
            title="Total Revenue"
            value={stats?.revenue ?? 0}
            prefix={<DollarOutlined />}
            loading={loading}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <RevenueChart />
        </Col>
        <Col xs={24} lg={8}>
          <PaymentMethodPieChart />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <UserGrowthChart />
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Recent Transactions">
            <Table
              rowKey="transaction_id"
              columns={recentColumns}
              dataSource={recent}
              loading={loading}
              pagination={false}
              size="small"
              scroll={{ x: 600 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
