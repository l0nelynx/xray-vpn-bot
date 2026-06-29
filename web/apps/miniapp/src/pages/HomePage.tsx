import { ArrowRightOutlined, LinkOutlined, ReloadOutlined, WifiOutlined } from "@ant-design/icons";
import { Button, Space } from "antd";
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MeResponse } from "../api/client";
import SubscriptionCard from "../components/SubscriptionCard";
import { openLink } from "../tg/webapp";

interface Props {
  me: MeResponse;
  reload: () => void;
  refresh: () => void;
}

export default function HomePage({ me, reload, refresh }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const sub = me.subscription;
  const username = me.user?.username;

  const lastReloadKey = useRef<string>("");
  useEffect(() => {
    const key = location.key || "default";
    if (lastReloadKey.current !== key) {
      lastReloadKey.current = key;
      refresh();
    }
  }, [location.key, refresh]);

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px" }}>
            {username ? `@${username}` : "Подписка"}
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.38)", marginTop: 2 }}>
            VPN аккаунт
          </div>
        </div>
        <Button
          className="refresh-fab"
          shape="circle"
          icon={<ReloadOutlined />}
          onClick={reload}
          aria-label="Обновить"
        />
      </div>

      {sub ? (
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <SubscriptionCard sub={sub} />

          {sub.status === "active" && sub.subscription_url && (
            <Button
              type="primary"
              size="large"
              block
              icon={<LinkOutlined />}
              onClick={() => openLink(sub.subscription_url!)}
            >
              Подключиться
            </Button>
          )}

          <Button
            size="large"
            block
            icon={<ArrowRightOutlined />}
            onClick={() => navigate("/buy")}
          >
            {sub.status === "active" ? "Продлить подписку" : "Купить подписку"}
          </Button>

          <Button
            size="large"
            block
            icon={<WifiOutlined />}
            onClick={() => navigate("/free/telemt")}
          >
            Telegram Прокси
          </Button>
        </Space>
      ) : (
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          {/* Empty state card */}
          <div style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.10)",
            borderRadius: 20,
            padding: "28px 20px",
            textAlign: "center",
          }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: 18,
              background: "linear-gradient(135deg, rgba(124,156,255,0.22), rgba(180,124,255,0.22))",
              border: "1px solid rgba(124,156,255,0.30)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 14px",
              fontSize: 24,
            }}>
              <WifiOutlined style={{ color: "#9DB8FF" }} />
            </div>
            <div style={{ fontSize: 17, fontWeight: 600, color: "#FFFFFF", marginBottom: 8 }}>
              Нет активной подписки
            </div>
            <div style={{ fontSize: 14, color: "rgba(255,255,255,0.45)", lineHeight: 1.5 }}>
              Выберите тариф или активируйте пробный доступ
            </div>
          </div>

          <Button type="primary" size="large" block onClick={() => navigate("/buy")}>
            Купить подписку
          </Button>
          <Button size="large" block onClick={() => navigate("/free/vpn")}>
            Попробовать бесплатно
          </Button>
          <Button size="large" block icon={<WifiOutlined />} onClick={() => navigate("/free/telemt")}>
            Telegram Прокси
          </Button>
        </Space>
      )}
    </div>
  );
}
