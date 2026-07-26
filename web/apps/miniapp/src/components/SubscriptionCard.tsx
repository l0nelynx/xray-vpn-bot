import { Laptop, Wifi } from "lucide-react";
import { Progress } from "@xray/ui/components/progress";
import { Badge } from "@xray/ui/components/badge";
import { SubscriptionInfo } from "../api/client";
import { useT } from "../i18n/LocaleContext";

interface Props {
  sub: SubscriptionInfo;
}

const STATUS_KEYS: Record<string, string> = {
  active: "subscription.status.active",
  expired: "subscription.status.expired",
  disabled: "subscription.status.disabled",
  limited: "subscription.status.limited",
  unavailable: "subscription.status.unavailable",
};

const STATUS_BADGE_VARIANT: Record<string, "success" | "destructive" | "secondary" | "warning"> = {
  active: "success",
  expired: "destructive",
  disabled: "secondary",
  limited: "warning",
  unavailable: "destructive",
};

export default function SubscriptionCard({ sub }: Props) {
  const { t, dateLocale } = useT();

  const statusKey = sub.status || "";
  const statusLabel = STATUS_KEYS[statusKey]
    ? t(STATUS_KEYS[statusKey])
    : statusKey || t("common.emDash");
  const statusVariant = STATUS_BADGE_VARIANT[statusKey] || "secondary";

  const usagePct =
    sub.data_limit_gb && sub.data_limit_gb > 0
      ? Math.min(100, Math.round((sub.traffic_used_gb / sub.data_limit_gb) * 100))
      : 0;

  const trafficLabel = sub.data_limit_gb
    ? t("common.gbUsedOfLimit", {
        used: sub.traffic_used_gb.toFixed(1),
        limit: sub.data_limit_gb,
      })
    : t("common.gbUsed", { used: sub.traffic_used_gb.toFixed(1) });

  const formatExpiry = (iso: string | null): string => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleDateString(dateLocale, {
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="sub-card">
      {/* Header: tariff name + status badge */}
      <div className="sub-card__header">
        <span className="sub-card__tariff">{sub.tariff}</span>
        <Badge variant={statusVariant}>{statusLabel}</Badge>
      </div>

      {/* Days remaining (large) */}
      <div className="sub-card__days-row">
        <span className="sub-card__days-num">{sub.days_left}</span>
        <span className="sub-card__days-label">{t("subscription.daysLeft")}</span>
      </div>

      {/* Traffic progress (only if limited) */}
      {sub.data_limit_gb ? (
        <div className="sub-card__progress">
          <Progress value={usagePct} className={usagePct >= 95 ? "progress-danger" : undefined} />
        </div>
      ) : (
        <div style={{ height: 12 }} />
      )}

      {/* Stats row */}
      <div className="sub-card__stats">
        <div className="sub-card__stat">
          <div className="sub-card__stat-val">
            <Laptop style={{ marginRight: 5, width: 14, height: 14, opacity: 0.7 }} />
            {sub.devices_count}
          </div>
          <div className="sub-card__stat-label">{t("subscription.devices")}</div>
        </div>

        <div className="sub-card__stat">
          <div className="sub-card__stat-val">
            <Wifi style={{ marginRight: 5, width: 14, height: 14, opacity: 0.7 }} />
            {trafficLabel}
          </div>
          <div className="sub-card__stat-label">{t("subscription.traffic")}</div>
        </div>

        {sub.expire_iso && (
          <div className="sub-card__stat">
            <div className="sub-card__stat-val" style={{ fontSize: 13 }}>
              {formatExpiry(sub.expire_iso)}
            </div>
            <div className="sub-card__stat-label">{t("subscription.expires")}</div>
          </div>
        )}
      </div>
    </div>
  );
}
