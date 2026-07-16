import { useEffect, useState, useMemo } from "react";
import { Card, Spin, Empty, Alert, Button } from "antd";
import { Column } from "@ant-design/charts";
import { api } from "../api/client";
import type { GrowthPoint } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

interface Props {
  period?: string;
}

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

  const chartHeight = isMobile ? 220 : 300;
  const isEmpty = !loading && !error && (data.length === 0 || data.every((d) => d.count === 0));

  if (loading)
    return (
      <Card style={{ minHeight: chartHeight + 80 }}>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: chartHeight }}>
          <Spin />
        </div>
      </Card>
    );

  return (
    <Card
      title={<span style={{ color: "rgba(255,255,255,0.85)" }}>User Growth</span>}
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button size="small" onClick={load}>
              Retry
            </Button>
          }
        />
      ) : isEmpty ? (
        <div style={{ height: chartHeight, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No data for this period" />
        </div>
      ) : (
        <Column
          data={chartData}
          xField="date"
          yField="count"
          height={chartHeight}
          style={{
            radiusTopLeft: 4,
            radiusTopRight: 4,
            fill: (d: Record<string, unknown>) =>
              (d as { _realCount: number })._realCount === 0
                ? "rgba(54,207,201,0.25)"
                : "#36cfc9",
            maxWidth: isMobile ? 16 : 32,
          }}
          axis={{
            x: {
              labelFill: "rgba(255,255,255,0.75)",
              labelFontSize: isMobile ? 9 : 11,
              labelAutoRotate: true,
              labelAutoHide: true,
              lineStroke: "rgba(255,255,255,0.12)",
              tick: false,
            },
            y: {
              labelFill: "rgba(255,255,255,0.75)",
              labelFontSize: isMobile ? 9 : 11,
              gridStroke: "rgba(255,255,255,0.08)",
              gridLineDash: [3, 3],
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
      )}
    </Card>
  );
}
