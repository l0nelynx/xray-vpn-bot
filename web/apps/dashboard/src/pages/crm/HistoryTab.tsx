import { App, Button, Card, Space, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import { fetchCampaigns } from "./api";
import type { CampaignSummary } from "./types";

export default function HistoryTab() {
  const { message } = App.useApp();
  const isMobile = useIsMobile();
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

  const perksLabel = (r: CampaignSummary) => {
    const parts: string[] = [];
    if (r.bonus_days) parts.push(`+${r.bonus_days}д`);
    if (r.bonus_traffic_gb) parts.push(`+${r.bonus_traffic_gb}ГБ`);
    if (!parts.length) return "—";
    return `${parts.join(", ")} (${r.perks_applied}/${r.perks_failed} ош.)`;
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
      render: (_: unknown, r: CampaignSummary) => perksLabel(r),
    },
    { title: "Создана", dataIndex: "created_at", key: "created_at", width: 170 },
  ];

  const renderMobileCampaignCard = (r: CampaignSummary) => (
    <Card
      key={r.id}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <Tag color={statusColor(r.status)} style={{ margin: 0 }}>
          {r.status}
        </Tag>
        <span style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>#{r.id}</span>
      </div>
      <div style={{ fontWeight: 600, color: "rgba(255,255,255,0.88)", marginBottom: 4 }}>
        {r.name || "—"}
      </div>
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4 }}>
        {r.segment_type ?? "—"} · {r.total_targets} целей
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 2 }}>
        Отправлено: {r.messages_sent} / ошибок: {r.messages_failed}
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 2 }}>
        Бонусы: {perksLabel(r)}
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
        {r.created_at || "—"}
      </div>
    </Card>
  );

  return (
    <Card
      title="История кампаний"
      extra={
        <Button onClick={load} loading={loading} block={isMobile}>
          Обновить
        </Button>
      }
    >
      {isMobile ? (
        loading ? (
          <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
            Загрузка...
          </div>
        ) : (
          <Space direction="vertical" style={{ width: "100%" }} size={0}>
            {campaigns.map(renderMobileCampaignCard)}
          </Space>
        )
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={campaigns}
          size="small"
          pagination={{ pageSize: 20 }}
        />
      )}
    </Card>
  );
}
