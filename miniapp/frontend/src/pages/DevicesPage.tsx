import { DeleteOutlined, ReloadOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Empty,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { api, DeviceItem, DevicesResponse } from "../api/client";

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  const load = () => {
    setDevices(null);
    setError(null);
    api
      .get<DevicesResponse>("/devices")
      .then((res) => setDevices(res.devices))
      .catch((e) => setError(e?.detail || String(e)));
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (hwid: string) => {
    setRemoving(hwid);
    try {
      await api.delete<void>(`/devices/${encodeURIComponent(hwid)}`);
      setDevices((prev) => (prev ? prev.filter((d) => d.hwid !== hwid) : prev));
      message.success("Устройство удалено");
    } catch (e: any) {
      Modal.error({
        title: "Не удалось удалить устройство",
        content: e?.detail || String(e),
      });
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <Typography.Title level={3} style={{ margin: 0 }}>
          Мои устройства
        </Typography.Title>
        <Button
          className="refresh-fab"
          shape="circle"
          icon={<ReloadOutlined />}
          onClick={load}
          aria-label="Обновить"
        />
      </div>

      {error && (
        <Alert type="error" title={error} style={{ marginBottom: 16 }} />
      )}

      {devices === null && !error && (
        <div className="spinner-wrap">
          <Spin />
        </div>
      )}

      {devices && devices.length === 0 && (
        <Empty description="Нет привязанных устройств" />
      )}

      {devices &&
        devices.map((d) => (
          <Card
            key={d.hwid}
            size="small"
            style={{ marginBottom: 12 }}
            title={
              <Space wrap>
                <span>{d.device_model || d.platform || "Устройство"}</span>
                {d.platform && <Tag color="blue">{d.platform}</Tag>}
              </Space>
            }
            extra={
              <Popconfirm
                title="Удалить устройство?"
                description="После удаления потребуется новая авторизация."
                okText="Удалить"
                cancelText="Отмена"
                okButtonProps={{ danger: true, loading: removing === d.hwid }}
                onConfirm={() => handleDelete(d.hwid)}
              >
                <Button
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  loading={removing === d.hwid}
                >
                  Удалить
                </Button>
              </Popconfirm>
            }
          >
            <Typography.Paragraph
              type="secondary"
              style={{ marginBottom: 4, fontSize: 12, wordBreak: "break-all" }}
            >
              HWID: {d.hwid}
            </Typography.Paragraph>
            {d.os_version && (
              <Typography.Paragraph style={{ marginBottom: 4 }}>
                ОС: {d.os_version}
              </Typography.Paragraph>
            )}
            <Typography.Paragraph
              type="secondary"
              style={{ marginBottom: 0, fontSize: 12 }}
            >
              Добавлено: {formatDate(d.created_at)}
            </Typography.Paragraph>
          </Card>
        ))}
    </div>
  );
}
