import { Card, Statistic } from "antd";
import type { ReactNode } from "react";

interface Props {
  title: string;
  value: number | string;
  prefix?: ReactNode;
  suffix?: string;
  loading?: boolean;
  color?: string;
}

export default function StatsCard({ title, value, prefix, suffix, loading, color = "#4f8cff" }: Props) {
  return (
    <Card
      style={{
        borderTop: `2px solid ${color}`,
      }}
      styles={{
        body: { padding: "20px 24px" },
      }}
    >
      <Statistic
        title={<span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>{title}</span>}
        value={value}
        prefix={<span style={{ color }}>{prefix}</span>}
        suffix={suffix}
        loading={loading}
        valueStyle={{ color: "rgba(255,255,255,0.95)", fontWeight: 600, fontSize: 28 }}
      />
    </Card>
  );
}
