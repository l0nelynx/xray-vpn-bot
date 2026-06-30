import { Skeleton } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";
import useIsMobile from "../hooks/useIsMobile";

interface Props {
  label: string;
  value: number;
  prev?: number;
  icon?: ReactNode;
  color?: string;
  /** Formats the main value (e.g. currency). Defaults to grouped integer. */
  format?: (v: number) => string;
  suffix?: string;
  loading?: boolean;
}

const GREEN = "#34D399";
const RED = "#F87171";
const MUTED = "rgba(255,255,255,0.35)";

const defaultFormat = (v: number) => Math.round(v).toLocaleString("en-US");

export default function MetricCard({
  label,
  value,
  prev,
  icon,
  color = "#6C8EFF",
  format = defaultFormat,
  suffix,
  loading,
}: Props) {
  const isMobile = useIsMobile();

  if (loading) {
    return (
      <div
        style={{
          background: "#111827",
          border: "1px solid #1E2540",
          borderRadius: 14,
          padding: isMobile ? "14px 16px" : "18px 20px",
          minHeight: isMobile ? 104 : 128,
        }}
      >
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
      </div>
    );
  }

  // Delta vs previous period
  let deltaPct: number | null = null;
  let isNew = false;
  if (prev != null) {
    if (prev === 0) {
      isNew = value > 0;
    } else {
      deltaPct = ((value - prev) / Math.abs(prev)) * 100;
    }
  }
  const up = deltaPct != null && deltaPct > 0.05;
  const down = deltaPct != null && deltaPct < -0.05;
  const deltaColor = up ? GREEN : down ? RED : MUTED;
  const DeltaIcon = up ? ArrowUpOutlined : down ? ArrowDownOutlined : MinusOutlined;

  return (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        background: "#111827",
        border: "1px solid #1E2540",
        borderRadius: 14,
        padding: isMobile ? "14px 16px" : "18px 20px",
        display: "flex",
        flexDirection: "column",
        gap: isMobile ? 8 : 10,
        minHeight: isMobile ? 104 : 128,
      }}
    >
      {/* Corner glow in the metric color for depth */}
      <div
        style={{
          position: "absolute",
          top: -40,
          right: -40,
          width: 120,
          height: 120,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 10,
            background: `${color}1f`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color,
            fontSize: 15,
          }}
        >
          {icon}
        </div>

        {(deltaPct != null || isNew) && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              fontSize: 11.5,
              fontWeight: 600,
              color: isNew ? GREEN : deltaColor,
              background: `${isNew ? GREEN : deltaColor}14`,
              padding: "2px 7px",
              borderRadius: 7,
              lineHeight: 1.4,
            }}
            title="vs previous period"
          >
            {isNew ? (
              "NEW"
            ) : (
              <>
                <DeltaIcon style={{ fontSize: 9 }} />
                {Math.abs(deltaPct!).toFixed(deltaPct! >= 100 || deltaPct! <= -100 ? 0 : 1)}%
              </>
            )}
          </div>
        )}
      </div>

      <div
        style={{
          fontSize: isMobile ? 21 : 26,
          fontWeight: 700,
          color: "#E2E8F8",
          letterSpacing: "-0.5px",
          lineHeight: 1.05,
        }}
      >
        {format(value)}
        {suffix && (
          <span style={{ fontSize: isMobile ? 12 : 14, fontWeight: 500, color: "rgba(255,255,255,0.4)", marginLeft: 4 }}>
            {suffix}
          </span>
        )}
      </div>

      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "rgba(255,255,255,0.35)",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
        }}
      >
        {label}
      </div>
    </div>
  );
}
