import { Alert, Button, Card, Col, Descriptions, Progress, Row, Spin, Tag, Typography } from "antd";
import { CalendarOutlined, LinkOutlined, ReloadOutlined, WifiOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { me, MeResponse, SubscriptionInfo } from "../../api/client";
import { useLang } from "../../locale";

const { Title, Text } = Typography;

function SubCard({ sub, L }: { sub: SubscriptionInfo; L: ReturnType<typeof useLang>["L"] }) {
  const usagePct =
    sub.data_limit_gb && sub.data_limit_gb > 0
      ? Math.min(100, Math.round((sub.traffic_used_gb / sub.data_limit_gb) * 100))
      : 0;

  const statusMap: Record<string, string> = {
    active: L.status_active,
    expired: L.status_expired,
    disabled: L.status_disabled,
    limited: L.status_limited,
  };
  const statusColorMap: Record<string, string> = {
    active: "success", expired: "error", disabled: "default", limited: "warning",
  };

  return (
    <Card
      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 16, marginBottom: 16 }}
    >
      <Row gutter={[24, 24]} align="middle">
        <Col xs={24} md={12}>
          <Descriptions column={1} size="small" colon={false} styles={{ label: { color: "rgba(255,255,255,0.5)", width: 160 } }}>
            <Descriptions.Item label={L.label_plan}>
              <Tag color="processing" style={{ fontWeight: 600 }}>{sub.tariff}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={L.label_status}>
              <Tag color={statusColorMap[sub.status || ""] || "default"}>
                {statusMap[sub.status || ""] || sub.status || "—"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label={L.label_days_left}>
              <Text strong style={{ color: "#fff", fontSize: 18 }}>{sub.days_left}</Text>
            </Descriptions.Item>
            {sub.expire_iso && (
              <Descriptions.Item label={L.label_expires}>
                <Text style={{ color: "rgba(255,255,255,0.75)" }}>
                  {new Date(sub.expire_iso).toLocaleDateString()}
                </Text>
              </Descriptions.Item>
            )}
            <Descriptions.Item label={L.label_devices}>{sub.devices_count}</Descriptions.Item>
            <Descriptions.Item label={L.label_traffic}>
              {sub.traffic_used_gb.toFixed(2)} / {sub.data_limit_gb ?? "∞"} GB
            </Descriptions.Item>
          </Descriptions>
        </Col>

        <Col xs={24} md={12}>
          {sub.data_limit_gb ? (
            <div>
              <Text style={{ color: "rgba(255,255,255,0.5)", fontSize: 13, display: "block", marginBottom: 8 }}>
                {L.traffic_usage}
              </Text>
              <Progress
                percent={usagePct}
                strokeColor={usagePct >= 90 ? "#ff4d4f" : "#06D6A0"}
                trailColor="rgba(255,255,255,0.1)"
                status={usagePct >= 95 ? "exception" : "active"}
              />
              <Text style={{ color: "rgba(255,255,255,0.4)", fontSize: 12 }}>
                {sub.traffic_used_gb.toFixed(2)} GB / {sub.data_limit_gb} GB
              </Text>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 24, background: "rgba(6,214,160,0.06)", borderRadius: 12, border: "1px solid rgba(6,214,160,0.15)" }}>
              <WifiOutlined style={{ fontSize: 32, color: "#06D6A0", marginBottom: 8 }} />
              <div style={{ color: "rgba(255,255,255,0.6)" }}>{L.traffic_unlimited}</div>
            </div>
          )}
        </Col>
      </Row>

      {sub.status === "active" && sub.subscription_url && (
        <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          <Button
            type="primary"
            icon={<LinkOutlined />}
            style={{ background: "linear-gradient(135deg, #06D6A0, #0096C7)", border: "none", borderRadius: 10 }}
            onClick={() => window.open(sub.subscription_url!, "_blank")}
          >
            {L.copy_sub_link}
          </Button>
        </div>
      )}
    </Card>
  );
}

export default function SubscriptionTab({ onBuyClick }: { onBuyClick: () => void }) {
  const { L } = useLang();
  const [data, setData] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setData(await me.get()); }
    catch { setError(L.err_load_sub); }
    finally { setLoading(false); }
  }, [L]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Title level={4} style={{ color: "#fff", margin: 0 }}>
          <WifiOutlined style={{ marginRight: 8 }} />{L.sub_title}
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
      ) : data?.subscription ? (
        <SubCard sub={data.subscription} L={L} />
      ) : (
        <div style={{ textAlign: "center", padding: "60px 24px", background: "rgba(255,255,255,0.03)", borderRadius: 16, border: "1px dashed rgba(255,255,255,0.1)" }}>
          <CalendarOutlined style={{ fontSize: 48, color: "rgba(255,255,255,0.2)", marginBottom: 16 }} />
          <Title level={4} style={{ color: "rgba(255,255,255,0.5)" }}>{L.no_sub_title}</Title>
          <Text style={{ color: "rgba(255,255,255,0.35)", display: "block", marginBottom: 24 }}>{L.no_sub_text}</Text>
          <Button type="primary" size="large" onClick={onBuyClick}
            style={{ background: "linear-gradient(135deg, #06D6A0, #0096C7)", border: "none", borderRadius: 12 }}>
            {L.btn_buy_sub}
          </Button>
        </div>
      )}
    </div>
  );
}
