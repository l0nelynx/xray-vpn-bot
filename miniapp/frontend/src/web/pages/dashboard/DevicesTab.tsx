import { Alert, Button, Card, Empty, Modal, Popconfirm, Spin, Table, Tag, Typography } from "antd";
import { DeleteOutlined, LaptopOutlined, MobileOutlined, ReloadOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { ApiError, devices, DeviceItem } from "../../api/client";
import { useLang } from "../../locale";

const { Title, Text } = Typography;

function platformIcon(platform: string | null) {
  const p = (platform || "").toLowerCase();
  if (p.includes("android") || p.includes("ios") || p.includes("mobile"))
    return <MobileOutlined style={{ color: "#06D6A0" }} />;
  return <LaptopOutlined style={{ color: "#06D6A0" }} />;
}

export default function DevicesTab() {
  const { L } = useLang();
  const [data, setData] = useState<{ total: number; devices: DeviceItem[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingHwid, setRemovingHwid] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { const resp = await devices.list(); setData(resp); }
    catch { setError(L.err_load_dev); }
    finally { setLoading(false); }
  }, [L]);

  useEffect(() => { load(); }, [load]);

  async function handleRemove(hwid: string) {
    setRemovingHwid(hwid);
    try {
      await devices.remove(hwid);
      await load();
    } catch (e) {
      const msg = e instanceof ApiError && e.status === 429 ? L.err_rate_limited_dev : L.err_remove_dev;
      Modal.error({ title: "Error", content: msg, centered: true });
    } finally {
      setRemovingHwid(null);
    }
  }

  const columns = [
    {
      title: L.col_device,
      dataIndex: "device_model",
      key: "device",
      render: (_: unknown, rec: DeviceItem) => (
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 20 }}>{platformIcon(rec.platform)}</span>
          <div>
            <div style={{ color: "#fff", fontWeight: 500 }}>{rec.device_model || L.unknown_device}</div>
            <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 12 }}>
              {[rec.platform, rec.os_version].filter(Boolean).join(" ")}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: L.col_platform,
      dataIndex: "platform",
      key: "platform",
      responsive: ["md" as const],
      render: (v: string | null) =>
        v ? <Tag>{v}</Tag> : <Text style={{ color: "rgba(255,255,255,0.3)" }}>—</Text>,
    },
    {
      title: L.col_added,
      dataIndex: "created_at",
      key: "created_at",
      responsive: ["lg" as const],
      render: (v: string | null) =>
        v ? (
          <Text style={{ color: "rgba(255,255,255,0.6)", fontSize: 13 }}>
            {new Date(v).toLocaleDateString()}
          </Text>
        ) : <Text style={{ color: "rgba(255,255,255,0.3)" }}>—</Text>,
    },
    {
      title: "",
      key: "actions",
      width: 60,
      render: (_: unknown, rec: DeviceItem) => (
        <Popconfirm
          title={L.confirm_remove}
          description={L.confirm_remove_desc}
          onConfirm={() => handleRemove(rec.hwid)}
          okText={L.ok_remove}
          cancelText={L.cancel}
          okButtonProps={{ danger: true }}
        >
          <Button danger icon={<DeleteOutlined />} size="small" loading={removingHwid === rec.hwid} style={{ borderRadius: 8 }} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Title level={4} style={{ color: "#fff", margin: 0 }}>
          <LaptopOutlined style={{ marginRight: 8 }} />
          {L.dev_title}
          {data && <Tag style={{ marginLeft: 8, verticalAlign: "middle" }}>{data.total}</Tag>}
        </Title>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}
          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.7)", borderRadius: 10 }}>
          {L.btn_refresh}
        </Button>
      </div>

      {loading && !data ? (
        <div style={{ textAlign: "center", padding: 60 }}><Spin size="large" /></div>
      ) : error ? (
        <Alert type="error" message={error} showIcon style={{ borderRadius: 12 }} />
      ) : (
        <Card
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 16 }}
          styles={{ body: { padding: 0 } }}
        >
          <Table
            dataSource={data?.devices || []}
            columns={columns}
            rowKey="hwid"
            pagination={false}
            locale={{ emptyText: <Empty description={<Text style={{ color: "rgba(255,255,255,0.35)" }}>{L.no_devices}</Text>} /> }}
            style={{ borderRadius: 16 }}
          />
        </Card>
      )}

      <Text style={{ display: "block", marginTop: 12, color: "rgba(255,255,255,0.3)", fontSize: 12 }}>
        {L.dev_auto_registered}
      </Text>
    </div>
  );
}
