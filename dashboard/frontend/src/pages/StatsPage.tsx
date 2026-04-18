import { useState, useEffect } from "react";
import { Row, Col, Select, Typography, Card, Tag, message } from "antd";
import RevenueChart from "../components/RevenueChart";
import UserGrowthChart from "../components/UserGrowthChart";
import PaymentMethodPieChart from "../components/PaymentMethodPieChart";
import StatsCard from "../components/StatsCard";
import { api } from "../api/client";
import type { OverviewStats, OrderStatusStat } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import { STATUS_COLORS, PERIOD_OPTIONS } from "../utils/constants";

export default function StatsPage() {
  const [period, setPeriod] = useState("month");
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [orderStatuses, setOrderStatuses] = useState<OrderStatusStat[]>([]);
  const [loading, setLoading] = useState(true);
  const isMobile = useIsMobile();

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview"),
      api.get<OrderStatusStat[]>("/stats/order-statuses"),
    ]).then(([s, os]) => {
      setStats(s);
      setOrderStatuses(os);
    }).catch(() => {
      message.error("Failed to load statistics");
    }).finally(() => {
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
          Statistics
        </Typography.Title>
        <Select
          value={period}
          onChange={setPeriod}
          style={{ width: 130 }}
          options={PERIOD_OPTIONS}
        />
      </div>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={24} sm={8}>
          <StatsCard title="Avg Order" value={stats?.avg_order ?? 0} loading={loading} color="#ff7a45" />
        </Col>
        <Col xs={12} sm={8}>
          <StatsCard title="Conversion" value={`${conversionRate}%`} loading={loading} color="#36cfc9" />
        </Col>
        <Col xs={12} sm={8}>
          <StatsCard title="Total Orders" value={totalOrders} loading={loading} color="#4f8cff" />
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
            title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Order Statuses</span>}
          >
            {orderStatuses.map((s) => (
              <div
                key={s.status}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 0",
                  borderBottom: "1px solid rgba(255,255,255,0.04)",
                }}
              >
                <Tag color={STATUS_COLORS[s.status] || "default"} style={{ margin: 0 }}>
                  {s.status}
                </Tag>
                <span style={{ color: "rgba(255,255,255,0.85)", fontWeight: 600, fontSize: 16 }}>
                  {s.count}
                </span>
              </div>
            ))}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
