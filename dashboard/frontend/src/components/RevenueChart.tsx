import { useEffect, useState } from "react";
import { Card, Spin } from "antd";
import { Line } from "@ant-design/charts";
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

  if (loading) return <Card><Spin /></Card>;

  return (
    <Card title="Revenue">
      <Line
        data={data}
        xField="date"
        yField="revenue"
        smooth
        height={300}
        point={{ size: 3 }}
        tooltip={{ channel: "y", valueFormatter: (v: number) => `${v}` }}
      />
    </Card>
  );
}
