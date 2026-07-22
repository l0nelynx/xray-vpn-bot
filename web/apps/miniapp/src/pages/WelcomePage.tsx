import { Rocket } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { LinksInfo } from "../api/client";
import { openTelegramLink } from "../tg/webapp";

interface Props {
  links: LinksInfo;
}

export default function WelcomePage({ links }: Props) {
  return (
    <div className="page page-centered">
      <div style={{ textAlign: "center", maxWidth: 320 }}>
        <Rocket style={{ width: 56, height: 56, color: "#52C41A", margin: "0 auto 20px" }} />
        <div style={{ fontSize: 20, fontWeight: 700, color: "#FFFFFF", marginBottom: 10 }}>
          Добро пожаловать!
        </div>
        <p style={{ color: "rgba(255,255,255,0.52)", marginBottom: 24, lineHeight: 1.5 }}>
          Чтобы пользоваться приложением, сначала запустите Telegram-бота и зарегистрируйтесь.
        </p>
        <Button size="lg" className="w-full" onClick={() => openTelegramLink(links.bot_url)}>
          Запустить бота
        </Button>
      </div>
    </div>
  );
}
