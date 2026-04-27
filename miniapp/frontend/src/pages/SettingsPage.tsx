import { LinksInfo } from "../api/client";
import { openLink, showAlert } from "../tg/webapp";

interface Props {
  links: LinksInfo;
  username: string;
}

export default function SettingsPage({ links, username }: Props) {
  return (
    <div className="page">
      <div className="page-title">Аккаунт</div>

      {username && (
        <div className="section">
          <div className="row">
            <span className="row-label">Telegram</span>
            <span className="row-value">@{username}</span>
          </div>
        </div>
      )}

      <div className="list-row" onClick={() => openLink(links.policy_url)}>
        <span>🔒 Политика конфиденциальности</span>
        <span className="chevron">›</span>
      </div>

      <div className="list-row" onClick={() => openLink(links.agreement_url)}>
        <span>📄 Пользовательское соглашение</span>
        <span className="chevron">›</span>
      </div>

      <div
        className="list-row"
        onClick={() =>
          showAlert("Раздел «Вход в аккаунт» появится в следующей версии.")
        }
      >
        <span>🔑 Вход в аккаунт</span>
        <span className="chevron">›</span>
      </div>
    </div>
  );
}
