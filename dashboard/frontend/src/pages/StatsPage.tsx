import { useState, useEffect } from "react";
import { Row, Col, Select, Space, Typography, Card } from "antd";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import StatsCard from "../components/StatsCard";
import { api } from "../api/client";
import type { OverviewStats, OrderStatusStat } from "../api/types";

export default function StatsPage() {
  const [period, setPeriod] = useState("day");
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [orderStatuses, setOrderStatuses] = useState<OrderStatusStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview"),
      api.get<OrderStatusStat[]>("/stats/order-statuses"),
    ]).then(([s, os]) => {
      setStats(s);
      setOrderStatuses(os);
      setLoading(false);
    });
  }, []);

  const totalOrders = orderStatuses.reduce((acc, s) => acc + s.count, 0);
  const confirmedOrders = orderStatuses
    .filter((s) => s.status === "confirmed" || s.status === "delivered")
    .reduce((acc, s) => acc + s.count, 0);
  const conversionRate = totalOrders > 0 ? ((confirmedOrders / totalOrders) * 100).toFixed(1) : "0";

  return (
    <div>
      <Space style={{ marginBottom: 16 }} align="center">
        <Typography.Title level={4} style={{ margin: 0 }}>
          Statistics
        </Typography.Title>
        <Select
          value={period}
          onChange={setPeriod}
          style={{ width: 120 }}
          options={[
            { value: "day", label: "Daily" },
            { value: "week", label: "Weekly" },
            { value: "month", label: "Monthly" },
          ]}
        />
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <StatsCard title="Avg Order" value={stats?.avg_order ?? 0} loading={loading} />
        </Col>
        <Col xs={24} sm={8}>
          <StatsCard title="Conversion Rate" value={`${conversionRate}%`} loading={loading} />
        </Col>
        <Col xs={24} sm={8}>
          <StatsCard title="Total Orders" value={totalOrders} loading={loading} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <RevenueChart period={period} />
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
          <Card title="Order Statuses">
            {orderStatuses.map((s) => (
              <div key={s.status} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <span>{s.status}</span>
                <strong>{s.count}</strong>
              </div>
            ))}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
