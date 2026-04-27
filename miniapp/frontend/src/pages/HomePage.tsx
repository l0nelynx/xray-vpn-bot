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
      <div className="page-title">Подписка</div>

      {sub ? (
        <>
          <SubscriptionCard sub={sub} />
          <button className="btn" onClick={() => open("extend")}>
            Продлить подписку
          </button>
          <button className="btn secondary" onClick={reload}>
            Обновить
          </button>
        </>
      ) : (
        <>
          <div className="section">
            <p style={{ color: "var(--hint)" }}>
              У вас пока нет подписки. Выберите тариф или активируйте пробную
              версию.
            </p>
          </div>
          <button className="btn" onClick={() => open("buy")}>
            Купить
          </button>
          <button className="btn secondary" onClick={() => open("trial")}>
            Пробная версия
          </button>
        </>
      )}
    </div>
  );
}
