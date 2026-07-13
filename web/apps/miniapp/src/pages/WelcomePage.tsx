import { RocketOutlined } from "@ant-design/icons";
import { Button, Result } from "antd";
import { LinksInfo } from "../api/client";
import { openTelegramLink } from "../tg/webapp";

interface Props {
  links: LinksInfo;
}

export default function WelcomePage({ links }: Props) {
  return (
    <div className="page page-centered">
      <Result
        icon={<RocketOutlined style={{ color: "#52C41A" }} />}
        title="Добро пожаловать!"
        subTitle="Чтобы пользоваться приложением, сначала запустите Telegram-бота и зарегистрируйтесь."
        extra={
          <Button
            type="primary"
            size="large"
            block
            onClick={() => openTelegramLink(links.bot_url)}
          >
            Запустить бота
          </Button>
        }
      />
    </div>
  );
}
