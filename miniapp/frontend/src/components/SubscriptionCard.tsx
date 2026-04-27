import { SubscriptionInfo } from "../api/client";

interface Props {
  sub: SubscriptionInfo;
}

const STATUS_LABELS: Record<string, string> = {
  active: "Активна",
  expired: "Истекла",
  disabled: "Отключена",
  limited: "Ограничена",
};

export default function SubscriptionCard({ sub }: Props) {
  const usagePct =
    sub.data_limit_gb && sub.data_limit_gb > 0
      ? Math.min(100, Math.round((sub.traffic_used_gb / sub.data_limit_gb) * 100))
      : 0;

  return (
    <div className="section">
      <div className="row">
        <span className="row-label">Тариф</span>
        <span className="row-value">{sub.tariff}</span>
      </div>
      <div className="row">
        <span className="row-label">Статус</span>
        <span className={`badge ${sub.status || "open"}`}>
          {(sub.status && STATUS_LABELS[sub.status]) || sub.status || "—"}
        </span>
      </div>
      <div className="row">
        <span className="row-label">Осталось дней</span>
        <span className="row-value">{sub.days_left}</span>
      </div>
      <div className="row">
        <span className="row-label">Устройства</span>
        <span className="row-value">{sub.devices_count}</span>
      </div>
      <div style={{ paddingTop: 12 }}>
        <div className="row" style={{ borderBottom: 0, paddingBottom: 4 }}>
          <span className="row-label">Трафик</span>
          <span className="row-value">
            {sub.traffic_used_gb} / {sub.data_limit_gb ?? "∞"} ГБ
          </span>
        </div>
        {sub.data_limit_gb && (
          <div className="progress">
            <div className="progress-bar" style={{ width: `${usagePct}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}
