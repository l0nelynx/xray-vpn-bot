import { useEffect, useState } from "react";
import { Card, Spin } from "antd";
import { Pie } from "@ant-design/charts";
import { api } from "../api/client";
import type { PaymentMethodStat } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

const COLORS = ["#4f8cff", "#36cfc9", "#ff7a45", "#ffc53d", "#b37feb", "#ff85c0"];

export default function PaymentMethodPieChart() {
  const [data, setData] = useState<PaymentMethodStat[]>([]);
  const [loading, setLoading] = useState(true);
  const isMobile = useIsMobile();

  useEffect(() => {
    api
      .get<PaymentMethodStat[]>("/stats/payment-methods")
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  const chartHeight = isMobile ? 220 : 300;

  if (loading)
    return (
      <Card style={{ minHeight: chartHeight + 80 }}>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: chartHeight }}>
          <Spin />
        </div>
      </Card>
    );

  return (
    <Card
      title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Payment Methods</span>}
    >
      <Pie
        data={data}
        angleField="count"
        colorField="method"
        height={chartHeight}
        innerRadius={0.6}
        color={COLORS}
        label={{
          text: "method",
          position: "outside",
          style: { fill: "rgba(255,255,255,0.7)", fontSize: isMobile ? 10 : 12 },
        }}
        legend={{
          color: {
            itemLabelFill: "rgba(255,255,255,0.7)",
          },
        }}
        tooltip={{ title: "method", items: [{ channel: "y" }] }}
      />
    </Card>
  );
}
