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

  if (loading) return <Card><Spin /></Card>;

  return (
    <Card title="User Growth">
      <Column
        data={data}
        xField="date"
        yField="count"
        height={300}
        tooltip={{ channel: "y", valueFormatter: (v: number) => `${v}` }}
      />
    </Card>
  );
}
