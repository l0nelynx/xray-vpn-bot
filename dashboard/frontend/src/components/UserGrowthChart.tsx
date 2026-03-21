import { useEffect, useState } from "react";
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
        data={data}
        xField="date"
        yField="count"
        height={300}
        style={{
          radiusTopLeft: 4,
          radiusTopRight: 4,
          fill: "#36cfc9",
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
          valueFormatter: (v: number) => `${v}`,
        }}
      />
    </Card>
  );
}
