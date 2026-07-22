import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import type { GrowthPoint } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import ChartCard from "./ChartCard";

interface Props {
  period?: string;
}

const AXIS = { fill: "oklch(0.68 0 0)", fontSize: 11 };
const GRID = "oklch(1 0 0 / 8%)";
const TOOLTIP = {
  background: "oklch(0.18 0 0)",
  border: "1px solid oklch(1 0 0 / 14%)",
  borderRadius: 8,
  color: "oklch(0.985 0 0)",
  fontSize: 12,
};

export default function UserGrowthChart({ period = "month" }: Props) {
  const [data, setData] = useState<GrowthPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMobile = useIsMobile();

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .get<GrowthPoint[]>(`/stats/user-growth?period=${period}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch(() => {
        setData([]);
        setError("Failed to load user growth chart");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const chartHeight = isMobile ? 240 : 280;
  const isEmpty = data.length === 0 || data.every((d) => d.count === 0);

  return (
    <ChartCard
      title="User Growth"
      description="New users over time."
      loading={loading}
      error={error}
      empty={isEmpty}
      onRetry={load}
      height={chartHeight}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tick={AXIS} stroke={GRID} tickMargin={8} />
          <YAxis tick={AXIS} stroke={GRID} tickMargin={8} width={40} />
          <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "oklch(1 0 0 / 4%)" }} />
          <Bar
            dataKey="count"
            fill="oklch(0.7 0 0)"
            radius={[4, 4, 0, 0]}
            maxBarSize={isMobile ? 18 : 28}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
