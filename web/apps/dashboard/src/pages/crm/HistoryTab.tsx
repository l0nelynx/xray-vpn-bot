import { App, Button, Card, Popconfirm, Space, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { fetchCampaigns } from "./api";
import type { CampaignSummary } from "./types";

export default function HistoryTab() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCampaigns(await fetchCampaigns());
    } catch {
      message.error("Не удалось загрузить историю");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    load();
  }, [load]);

  const statusColor = (s: string) => {
    if (s === "completed") return "green";
    if (s === "running") return "processing";
    if (s === "queued") return "blue";
    if (s === "failed") return "red";
    return "default";
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 70 },
    { title: "Название", dataIndex: "name", key: "name", ellipsis: true },
    {
      title: "Сегмент",
      dataIndex: "segment_type",
      key: "segment_type",
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "Статус",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColor(v)}>{v}</Tag>,
    },
    { title: "Целей", dataIndex: "total_targets", key: "total_targets", width: 80 },
    {
      title: "Отправлено",
      key: "sent",
      render: (_: unknown, r: CampaignSummary) =>
        `${r.messages_sent} / ${r.messages_failed} ош.`,
    },
    {
      title: "Бонусы",
      key: "perks",
      render: (_: unknown, r: CampaignSummary) => {
        const parts: string[] = [];
        if (r.bonus_days) parts.push(`+${r.bonus_days}д`);
        if (r.bonus_traffic_gb) parts.push(`+${r.bonus_traffic_gb}ГБ`);
        if (!parts.length) return "—";
        return `${parts.join(", ")} (${r.perks_applied}/${r.perks_failed} ош.)`;
      },
    },
    { title: "Создана", dataIndex: "created_at", key: "created_at", width: 170 },
  ];

  return (
    <Card
      title="История кампаний"
      extra={
        <Button onClick={load} loading={loading}>
          Обновить
        </Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={campaigns}
        size="small"
        pagination={{ pageSize: 20 }}
      />
    </Card>
  );
}
