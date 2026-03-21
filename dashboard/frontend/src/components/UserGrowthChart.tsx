import { useEffect, useState } from "react";
import { Card, Spin } from "antd";
import { Column } from "@ant-design/charts";
import { api } from "../api/client";
import type { GrowthPoint } from "../api/types";

export default function UserGrowthChart() {
  const [data, setData] = useState<GrowthPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<GrowthPoint[]>("/stats/user-growth")
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

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
        color="#36cfc9"
        columnStyle={{
          radius: [4, 4, 0, 0],
          fill: "l(270) 0:#36cfc9 1:rgba(54,207,201,0.3)",
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
