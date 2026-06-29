import { Skeleton } from "antd";
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

export default function StatsCard({
  title,
  value,
  prefix,
  suffix,
  loading,
  color = "#6C8EFF",
}: Props) {
  const isMobile = useIsMobile();

  const formattedValue =
    typeof value === "number"
      ? Math.round(value).toLocaleString("en-US")
      : value;

  if (loading) {
    return (
      <div
        style={{
          background: "#111827",
          border: "1px solid #1E2540",
          borderRadius: 12,
          padding: isMobile ? "14px 16px" : "18px 20px",
        }}
      >
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
      </div>
    );
  }

  return (
    <div
      style={{
        background: "#111827",
        border: "1px solid #1E2540",
        borderRadius: 12,
        padding: isMobile ? "14px 16px" : "18px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      {/* Icon pill */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: `${color}18`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color,
          fontSize: 16,
        }}
      >
        {prefix}
      </div>

      {/* Value */}
      <div
        style={{
          fontSize: isMobile ? 22 : 26,
          fontWeight: 700,
          color: "#E2E8F8",
          letterSpacing: "-0.5px",
          lineHeight: 1,
        }}
      >
        {formattedValue}
        {suffix && (
          <span
            style={{
              fontSize: isMobile ? 13 : 15,
              fontWeight: 500,
              color: "rgba(255,255,255,0.4)",
              marginLeft: 4,
            }}
          >
            {suffix}
          </span>
        )}
      </div>

      {/* Label */}
      <div
        style={{
          fontSize: 11.5,
          fontWeight: 600,
          color: "rgba(255,255,255,0.35)",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
        }}
      >
        {title}
      </div>
    </div>
  );
}
