import { useEffect, useState } from "react";
import { Card, Spin } from "antd";
import { Pie } from "@ant-design/charts";
import { api } from "../api/client";
import type { PaymentMethodStat } from "../api/types";

export default function PaymentMethodPieChart() {
  const [data, setData] = useState<PaymentMethodStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<PaymentMethodStat[]>("/stats/payment-methods")
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Card><Spin /></Card>;

  return (
    <Card title="Payment Methods">
      <Pie
        data={data}
        angleField="count"
        colorField="method"
        height={300}
        innerRadius={0.6}
        label={{ text: "method", position: "outside" }}
        tooltip={{ title: "method", items: [{ channel: "y" }] }}
      />
    </Card>
  );
}
