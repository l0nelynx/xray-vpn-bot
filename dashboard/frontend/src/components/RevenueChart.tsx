import { useEffect, useState } from "react";
import { Card, Spin } from "antd";
import { Column } from "@ant-design/charts";
import { api } from "../api/client";
import type { RevenuePoint } from "../api/types";

interface Props {
  period?: string;
}

export default function RevenueChart({ period = "day" }: Props) {
  const [data, setData] = useState<RevenuePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<RevenuePoint[]>(`/stats/revenue?period=${period}`)
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
      title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Revenue</span>}
    >
      <Column
        data={data}
        xField="date"
        yField="revenue"
        height={300}
        color="#4f8cff"
        columnStyle={{
          radius: [4, 4, 0, 0],
          fill: "l(270) 0:#4f8cff 1:rgba(79,140,255,0.3)",
        }}
        xAxis={{
          label: {
            style: { fill: "rgba(255,255,255,0.45)", fontSize: 11 },
          },
          line: { style: { stroke: "rgba(255,255,255,0.06)" } },
          tickLine: null,
        }}
        yAxis={{
          label: {
            style: { fill: "rgba(255,255,255,0.45)", fontSize: 11 },
          },
          grid: {
            line: { style: { stroke: "rgba(255,255,255,0.06)", lineDash: [3, 3] } },
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
