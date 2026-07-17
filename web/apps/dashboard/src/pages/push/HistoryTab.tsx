import { App, Button, Card, Space, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import { fetchPushCampaigns, type PushCampaignSummary } from "./api";

export default function HistoryTab() {
  const { message } = App.useApp();
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<PushCampaignSummary[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCampaigns(await fetchPushCampaigns());
    } catch {
      message.error("Failed to load push history");
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

  const audienceLabel = (r: PushCampaignSummary) => {
    if (r.audience === "user_ids") {
      const n = r.audience_params?.user_ids?.length ?? 0;
      return `user_ids (${n})`;
    }
    return "all_tokens";
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 70 },
    { title: "Title", dataIndex: "title", key: "title", ellipsis: true },
    {
      title: "Audience",
      key: "audience",
      render: (_: unknown, r: PushCampaignSummary) => audienceLabel(r),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColor(v)}>{v}</Tag>,
    },
    { title: "Targets", dataIndex: "total_targets", key: "total_targets", width: 80 },
    {
      title: "Sent",
      key: "sent",
      render: (_: unknown, r: PushCampaignSummary) =>
        `${r.sent} / ${r.failed} failed`,
    },
    { title: "Created", dataIndex: "created_at", key: "created_at", width: 170 },
    { title: "By", dataIndex: "created_by", key: "created_by", ellipsis: true },
  ];

  const renderMobileCard = (r: PushCampaignSummary) => (
    <Card
      key={r.id}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <Tag color={statusColor(r.status)} style={{ margin: 0 }}>
          {r.status}
        </Tag>
        <span style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>#{r.id}</span>
      </div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{r.title || "—"}</div>
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4 }}>
        {audienceLabel(r)} · {r.total_targets} targets
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
        Sent: {r.sent} / failed: {r.failed}
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
        {r.created_at || "—"}
      </div>
    </Card>
  );

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button onClick={load} loading={loading}>
          Refresh
        </Button>
      </Space>
      {isMobile ? (
        <div>
          {campaigns.length === 0 && !loading ? (
            <Card size="small">No push campaigns yet</Card>
          ) : (
            campaigns.map(renderMobileCard)
          )}
        </div>
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          dataSource={campaigns}
          columns={columns}
          pagination={{ pageSize: 20 }}
          size="middle"
        />
      )}
    </div>
  );
}
