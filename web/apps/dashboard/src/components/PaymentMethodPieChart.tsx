import { useEffect, useState } from "react";
import { Card, Spin, Empty, Alert, Button } from "antd";
import { Pie } from "@ant-design/charts";
import { api } from "../api/client";
import type { PaymentMethodStat } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

const COLORS = ["#7C9CFF", "#36cfc9", "#ff7a45", "#ffc53d", "#b37feb", "#ff85c0"];

export default function PaymentMethodPieChart() {
  const [data, setData] = useState<PaymentMethodStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMobile = useIsMobile();

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .get<PaymentMethodStat[]>("/stats/payment-methods")
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch(() => {
        setData([]);
        setError("Failed to load payment methods");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const chartHeight = isMobile ? 220 : 300;
  const isEmpty = !loading && !error && (data.length === 0 || data.every((d) => d.count === 0));

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
      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button size="small" onClick={load}>
              Retry
            </Button>
          }
        />
      ) : isEmpty ? (
        <div style={{ height: chartHeight, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No data for this period" />
        </div>
      ) : (
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
            fill: "rgba(255,255,255,0.8)",
            fontSize: isMobile ? 10 : 12,
          }}
          legend={{
            color: {
              itemLabelFill: "rgba(255,255,255,0.8)",
              itemLabelFontSize: isMobile ? 11 : 12,
            },
          }}
          tooltip={{ title: "method", items: [{ channel: "y" }] }}
        />
      )}
    </Card>
  );
}
