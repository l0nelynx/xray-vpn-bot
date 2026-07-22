import { useEffect, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "../api/client";
import type { PaymentMethodStat } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import ChartCard from "./ChartCard";

const COLORS = [
  "oklch(0.92 0 0)",
  "oklch(0.7 0 0)",
  "oklch(0.55 0 0)",
  "oklch(0.42 0 0)",
  "oklch(0.696 0.12 160)",
  "oklch(0.75 0.12 75)",
];

const TOOLTIP = {
  background: "oklch(0.18 0 0)",
  border: "1px solid oklch(1 0 0 / 14%)",
  borderRadius: 8,
  color: "oklch(0.985 0 0)",
  fontSize: 12,
};

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

  const chartHeight = isMobile ? 240 : 280;
  const isEmpty = data.length === 0 || data.every((d) => d.count === 0);

  return (
    <ChartCard
      title="Payment Methods"
      description="Share of orders by gateway."
      loading={loading}
      error={error}
      empty={isEmpty}
      onRetry={load}
      height={chartHeight}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
          <Pie
            data={data}
            dataKey="count"
            nameKey="method"
            innerRadius="52%"
            outerRadius="72%"
            paddingAngle={3}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip contentStyle={TOOLTIP} />
          <Legend
            verticalAlign="bottom"
            height={36}
            wrapperStyle={{ fontSize: 12, color: "oklch(0.68 0 0)" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
