import { LinkOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Space, Typography } from "antd";
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

  // Silently refresh whenever the user lands on "/", including on remounts
  // after the user navigates back from another screen.
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
      <div className="page-header">
        <Typography.Title level={3} style={{ margin: 0 }}>
          Подписка
        </Typography.Title>
        <Button
          className="refresh-fab"
          shape="circle"
          icon={<ReloadOutlined />}
          onClick={reload}
          aria-label="Обновить"
        />
      </div>

      {sub ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
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
          <Button size="large" block onClick={() => navigate("/buy")}>
            Продлить подписку
          </Button>
          <Button size="large" block onClick={() => navigate("/free/telemt")}>
            Telegram Прокси
          </Button>
        </Space>
      ) : (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Paragraph type="secondary">
            У вас пока нет подписки. Выберите тариф или активируйте пробную версию.
          </Typography.Paragraph>
          <Button type="primary" size="large" block onClick={() => navigate("/buy")}>
            Купить
          </Button>
          <Button size="large" block onClick={() => navigate("/free/vpn")}>
            Попробовать Бесплатно
          </Button>
          <Button size="large" block onClick={() => navigate("/free/telemt")}>
            Telegram Прокси
          </Button>
        </Space>
      )}
    </div>
  );
}
