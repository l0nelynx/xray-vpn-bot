import { Button, Space, Typography } from "antd";
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MeResponse } from "../api/client";
import SubscriptionCard from "../components/SubscriptionCard";

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
      <Typography.Title level={3} style={{ marginBottom: 20 }}>
        Подписка
      </Typography.Title>

      {sub ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <SubscriptionCard sub={sub} />
          <Button type="primary" size="large" block onClick={() => navigate("/buy")}>
            Продлить подписку
          </Button>
          <Button size="large" block onClick={() => navigate("/devices")}>
            Мои устройства
          </Button>
          <Button size="large" block onClick={() => navigate("/free/telemt")}>
            Telegram Прокси
          </Button>
          <Button size="large" block onClick={reload}>
            Обновить
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
          <Button size="large" block onClick={reload}>
            Обновить
          </Button>
        </Space>
      )}
    </div>
  );
}
