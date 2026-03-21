import { useEffect, useState, useMemo } from "react";
import { Card, Spin } from "antd";
import { Column } from "@ant-design/charts";
import { api } from "../api/client";
import type { GrowthPoint } from "../api/types";

interface Props {
  period?: string;
}

export default function UserGrowthChart({ period = "month" }: Props) {
  const [data, setData] = useState<GrowthPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<GrowthPoint[]>(`/stats/user-growth?period=${period}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [period]);

  // Replace zero values with a small visual minimum so stems are always visible
  const chartData = useMemo(() => {
    const maxVal = Math.max(...data.map((d) => d.count), 1);
    const minVisible = maxVal * 0.015;
    return data.map((d) => ({
      ...d,
      _realCount: d.count,
      count: d.count === 0 ? minVisible : d.count,
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
      title={<span style={{ color: "rgba(255,255,255,0.85)" }}>User Growth</span>}
    >
      <Column
        data={chartData}
        xField="date"
        yField="count"
        height={300}
        style={{
          radiusTopLeft: 4,
          radiusTopRight: 4,
          fill: (d: Record<string, unknown>) =>
            (d as { _realCount: number })._realCount === 0
              ? "rgba(54,207,201,0.25)"
              : "#36cfc9",
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
            const real = (datum as { _realCount?: number })?._realCount;
            return `${real ?? _v}`;
          },
        }}
      />
    </Card>
  );
}
