import { useEffect, useState, useMemo } from "react";
import { Card, Spin } from "antd";
import { Column } from "@ant-design/charts";
import { api } from "../api/client";
import type { RevenuePoint } from "../api/types";

interface Props {
  period?: string;
}

export default function RevenueChart({ period = "month" }: Props) {
  const [data, setData] = useState<RevenuePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<RevenuePoint[]>(`/stats/revenue?period=${period}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [period]);

  // Replace zero values with a small visual minimum so stems are always visible
  const chartData = useMemo(() => {
    const maxVal = Math.max(...data.map((d) => d.revenue), 1);
    const minVisible = maxVal * 0.015; // 1.5% of max
    return data.map((d) => ({
      ...d,
      _realRevenue: d.revenue,
      revenue: d.revenue === 0 ? minVisible : d.revenue,
    }));
  }, [data]);

  if (loading)
    return (
      <Card style={{ minHeight: 380 }}>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 300 }}>
          <Spin />
        </div>
      </Card>
    );

  return (
    <Card
      title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Revenue</span>}
    >
      <Column
        data={chartData}
        xField="date"
        yField="revenue"
        height={300}
        style={{
          radiusTopLeft: 4,
          radiusTopRight: 4,
          fill: (d: Record<string, unknown>) =>
            (d as { _realRevenue: number })._realRevenue === 0
              ? "rgba(79,140,255,0.25)"
              : "#4f8cff",
          maxWidth: 32,
        }}
        axis={{
          x: {
            label: {
              style: { fill: "rgba(255,255,255,0.65)", fontSize: 11 },
              autoRotate: true,
            },
            line: { style: { stroke: "rgba(255,255,255,0.1)" } },
            tick: null,
          },
          y: {
            label: {
              style: { fill: "rgba(255,255,255,0.65)", fontSize: 11 },
            },
            grid: {
              style: { stroke: "rgba(255,255,255,0.08)", lineDash: [3, 3] },
            },
          },
        }}
        tooltip={{
          channel: "y",
          valueFormatter: (_v: number, datum: Record<string, unknown>) => {
            const real = (datum as { _realRevenue?: number })?._realRevenue;
            return `${real ?? _v}`;
          },
        }}
      />
    </Card>
  );
}
