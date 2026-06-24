import { Progress, Tag } from "antd";
import { LaptopOutlined, WifiOutlined } from "@ant-design/icons";
import { SubscriptionInfo } from "../api/client";

interface Props {
  sub: SubscriptionInfo;
}

const STATUS_LABELS: Record<string, string> = {
  active:   "Активна",
  expired:  "Истекла",
  disabled: "Отключена",
  limited:  "Ограничена",
};

const STATUS_TAG_COLOR: Record<string, string> = {
  active:   "success",
  expired:  "error",
  disabled: "default",
  limited:  "warning",
};

function formatExpiry(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function SubscriptionCard({ sub }: Props) {
  const statusKey = sub.status || "";
  const statusLabel = STATUS_LABELS[statusKey] || statusKey || "—";
  const statusTagColor = STATUS_TAG_COLOR[statusKey] || "default";

  const usagePct =
    sub.data_limit_gb && sub.data_limit_gb > 0
      ? Math.min(100, Math.round((sub.traffic_used_gb / sub.data_limit_gb) * 100))
      : 0;

  const trafficLabel = sub.data_limit_gb
    ? `${sub.traffic_used_gb.toFixed(1)} / ${sub.data_limit_gb} ГБ`
    : `${sub.traffic_used_gb.toFixed(1)} ГБ`;

  return (
    <div className="sub-card">
      {/* Header: tariff name + status badge */}
      <div className="sub-card__header">
        <span className="sub-card__tariff">{sub.tariff}</span>
        <Tag color={statusTagColor} style={{ margin: 0, fontWeight: 600 }}>
          {statusLabel}
        </Tag>
      </div>

      {/* Days remaining (large) */}
      <div className="sub-card__days-row">
        <span className="sub-card__days-num">{sub.days_left}</span>
        <span className="sub-card__days-label">дней осталось</span>
      </div>

      {/* Traffic progress (only if limited) */}
      {sub.data_limit_gb ? (
        <div className="sub-card__progress">
          <Progress
            percent={usagePct}
            status={usagePct >= 95 ? "exception" : "active"}
            showInfo={false}
            strokeWidth={5}
          />
        </div>
      ) : (
        <div style={{ height: 12 }} />
      )}

      {/* Stats row */}
      <div className="sub-card__stats">
        <div className="sub-card__stat">
          <div className="sub-card__stat-val">
            <LaptopOutlined style={{ marginRight: 5, fontSize: 14, opacity: 0.7 }} />
            {sub.devices_count}
          </div>
          <div className="sub-card__stat-label">Устройства</div>
        </div>

        <div className="sub-card__stat">
          <div className="sub-card__stat-val">
            <WifiOutlined style={{ marginRight: 5, fontSize: 14, opacity: 0.7 }} />
            {trafficLabel}
          </div>
          <div className="sub-card__stat-label">Трафик</div>
        </div>

        {sub.expire_iso && (
          <div className="sub-card__stat">
            <div className="sub-card__stat-val" style={{ fontSize: 13 }}>
              {formatExpiry(sub.expire_iso)}
            </div>
            <div className="sub-card__stat-label">Истекает</div>
          </div>
        )}
      </div>
    </div>
  );
}
