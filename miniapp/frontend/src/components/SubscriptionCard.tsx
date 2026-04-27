import { Card, Descriptions, Progress, Tag } from "antd";
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

const STATUS_COLOR: Record<string, string> = {
  active: "success",
  expired: "error",
  disabled: "default",
  limited: "warning",
};

export default function SubscriptionCard({ sub }: Props) {
  const usagePct =
    sub.data_limit_gb && sub.data_limit_gb > 0
      ? Math.min(100, Math.round((sub.traffic_used_gb / sub.data_limit_gb) * 100))
      : 0;

  const statusKey = sub.status || "";
  const statusLabel = STATUS_LABELS[statusKey] || statusKey || "—";
  const statusColor = STATUS_COLOR[statusKey] || "default";

  return (
    <Card style={{ marginBottom: 16 }}>
      <Descriptions column={1} size="small" colon={false} labelStyle={{ width: 140 }}>
        <Descriptions.Item label="Тариф">
          <Tag color="processing" style={{ fontWeight: 600 }}>
            {sub.tariff}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Статус">
          <Tag color={statusColor}>{statusLabel}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Осталось дней">
          <b>{sub.days_left}</b>
        </Descriptions.Item>
        <Descriptions.Item label="Устройства">{sub.devices_count}</Descriptions.Item>
        <Descriptions.Item label="Трафик">
          {sub.traffic_used_gb} / {sub.data_limit_gb ?? "∞"} ГБ
        </Descriptions.Item>
      </Descriptions>
      {sub.data_limit_gb ? (
        <Progress percent={usagePct} status={usagePct >= 95 ? "exception" : "active"} />
      ) : null}
    </Card>
  );
}
