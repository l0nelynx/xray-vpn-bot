import { LinksInfo } from "../api/client";
import { openTelegramLink } from "../tg/webapp";

interface Props {
  links: LinksInfo;
}

export default function WelcomePage({ links }: Props) {
  return (
    <div className="welcome">
      <h1>Добро пожаловать!</h1>
      <p>
        Чтобы пользоваться приложением, сначала запустите Telegram-бота и
        зарегистрируйтесь.
      </p>
      <button className="btn" onClick={() => openTelegramLink(links.bot_url)}>
        Запустить бота
      </button>
    </div>
  );
}
