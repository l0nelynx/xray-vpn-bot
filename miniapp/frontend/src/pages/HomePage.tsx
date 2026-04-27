import { Button, Space, Typography } from "antd";
import { MeResponse } from "../api/client";
import SubscriptionCard from "../components/SubscriptionCard";
import { openTelegramLink } from "../tg/webapp";

interface Props {
  me: MeResponse;
  reload: () => void;
}

export default function HomePage({ me, reload }: Props) {
  const botUrl = me.links.bot_url;
  const sub = me.subscription;

  const open = (suffix: string) => {
    if (!botUrl) return;
    const sep = botUrl.includes("?") ? "&" : "?";
    openTelegramLink(`${botUrl}${sep}start=${suffix}`);
  };

  return (
    <div className="page">
      <Typography.Title level={3} style={{ marginBottom: 20 }}>
        Подписка
      </Typography.Title>

      {sub ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <SubscriptionCard sub={sub} />
          <Button type="primary" size="large" block onClick={() => open("extend")}>
            Продлить подписку
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
          <Button type="primary" size="large" block onClick={() => open("buy")}>
            Купить
          </Button>
          <Button size="large" block onClick={() => open("trial")}>
            Пробная версия
          </Button>
        </Space>
      )}
    </div>
  );
}
