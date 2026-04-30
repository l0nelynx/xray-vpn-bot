import LegalLayout from "../components/LegalLayout";
import { LinksInfo } from "../api/client";

interface Props {
  links: LinksInfo;
}

export default function AgreementPage({ links }: Props) {
  const brand = links.branding_name || "VPN";
  const supportLink = links.support_bot_link;
  const supportLabel = supportLink
    ? supportLink.split("/").pop() || supportLink
    : "поддержка";

  return (
    <LegalLayout title="Пользовательское соглашение">
      <section className="legal-section">
        <h2>1. Предмет соглашения</h2>
        <p>
          1.1. Сервис {brand} предоставляет доступ к VPN-серверам через
          Telegram-бота для шифрования интернет-трафика.
        </p>
        <p>
          1.2. Услуги доступны только совершеннолетним пользователям.
          Использование бота означает акцепт оферты.
        </p>
      </section>

      <section className="legal-section">
        <h2>2. Условия использования</h2>
        <p>2.1. Пользователь обязуется:</p>
        <ul>
          <li>
            Не нарушать законы РФ (включая обход блокировок запрещённых
            ресурсов: экстремистские материалы, наркотики и т. д.);
          </li>
          <li>Не распространять вредоносное ПО;</li>
          <li>Не использовать сервис для DDoS-атак, спама или взлома.</li>
        </ul>
        <p>
          <strong>2.2. Запрещено:</strong>
        </p>
        <ul>
          <li>Передавать аккаунт третьим лицам;</li>
          <li>Мешать работе сервиса.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>3. Оплата и возврат</h2>
        <p>
          3.1. Оплата тарифов осуществляется через Telegram-бота (карты, Qiwi,
          криптовалюты).
        </p>
        <p>
          3.2. Возврат средств возможен только при технической невозможности
          предоставить услугу.
        </p>
      </section>

      <section className="legal-section">
        <h2>4. Ответственность</h2>
        <p>4.1. Сервис не гарантирует 100% доступность VPN.</p>
        <p>4.2. Администрация не несёт ответственности за:</p>
        <ul>
          <li>Нелегальные действия пользователей;</li>
          <li>Ущерб из-за сбоев VPN;</li>
          <li>Блокировку доступа к ресурсам.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>5. Расторжение</h2>
        <p>
          5.1. Администрация вправе заблокировать аккаунт при нарушении п. 2 без
          возврата средств.
        </p>
        <p>5.2. Пользователь может отказаться от услуг, прекратив оплату.</p>
      </section>

      <section className="legal-section">
        <h2>6. Контакты</h2>
        <p>
          Поддержка:{" "}
          {supportLink ? (
            <a href={supportLink} target="_blank" rel="noreferrer">
              {supportLabel}
            </a>
          ) : (
            <span>{supportLabel}</span>
          )}
        </p>
      </section>

      <div className="legal-callout">
        Используя сервис {brand}, вы подтверждаете, что ознакомились и согласны
        с условиями данного соглашения.
      </div>
    </LegalLayout>
  );
}
