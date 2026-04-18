import { Card, Statistic } from "antd";
import type { ReactNode } from "react";
import useIsMobile from "../hooks/useIsMobile";

interface Props {
  title: string;
  value: number | string;
  prefix?: ReactNode;
  suffix?: string;
  loading?: boolean;
  color?: string;
}

export default function StatsCard({ title, value, prefix, suffix, loading, color = "#4f8cff" }: Props) {
  const isMobile = useIsMobile();

  return (
    <Card
      style={{
        borderTop: `2px solid ${color}`,
      }}
      styles={{
        body: { padding: isMobile ? "12px 14px" : "20px 24px" },
      }}
    >
      <Statistic
        title={<span style={{ color: "rgba(255,255,255,0.5)", fontSize: isMobile ? 11 : 13 }}>{title}</span>}
        value={value}
        prefix={isMobile ? null : <span style={{ color }}>{prefix}</span>}
        suffix={suffix}
        loading={loading}
        valueStyle={{
          color: "rgba(255,255,255,0.95)",
          fontWeight: 600,
          fontSize: isMobile ? 20 : 28,
        }}
      />
    </Card>
  );
}
