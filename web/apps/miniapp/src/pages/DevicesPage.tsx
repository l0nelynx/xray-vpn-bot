import { DeleteOutlined, LaptopOutlined, MobileOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Modal, Popconfirm, Spin, Tag, App } from "antd";
import { useEffect, useState } from "react";
import { api, DeviceItem, DevicesResponse } from "../api/client";

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

function platformIcon(platform: string | null): React.ReactNode {
  if (!platform) return <LaptopOutlined />;
  const p = platform.toLowerCase();
  if (p.includes("android") || p.includes("ios") || p.includes("iphone") || p.includes("mobile")) {
    return <MobileOutlined />;
  }
  return <LaptopOutlined />;
}

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const { message } = App.useApp();

  const load = () => {
    setDevices(null);
    setError(null);
    api
      .get<DevicesResponse>("/devices")
      .then((res) => setDevices(res.devices))
      .catch((e) => setError(e?.detail || String(e)));
  };

  useEffect(() => { load(); }, []);

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
        <span style={{ fontSize: 22, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px" }}>
          Мои устройства
        </span>
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

      {devices && devices.map((d) => (
        <div key={d.hwid} className="device-card">
          <div className="device-card__icon">
            {platformIcon(d.platform)}
          </div>

          <div className="device-card__body">
            <div className="device-card__name">
              {d.device_model || d.platform || "Устройство"}
              {d.platform && (
                <Tag color="processing" style={{ marginLeft: 8, fontSize: 11, verticalAlign: "middle" }}>
                  {d.platform}
                </Tag>
              )}
            </div>
            {d.os_version && (
              <div className="device-card__meta">ОС: {d.os_version}</div>
            )}
            <div className="device-card__meta" style={{ marginTop: 4 }}>
              Добавлено: {formatDate(d.created_at)}
            </div>
            <div className="device-card__meta" style={{ opacity: 0.6, marginTop: 2, fontSize: 11 }}>
              {d.hwid}
            </div>
          </div>

          <div className="device-card__actions">
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
                shape="circle"
                icon={<DeleteOutlined />}
                loading={removing === d.hwid}
              />
            </Popconfirm>
          </div>
        </div>
      ))}
    </div>
  );
}
