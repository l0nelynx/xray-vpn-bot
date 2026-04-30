import LegalLayout from "../components/LegalLayout";
import { LinksInfo } from "../api/client";

interface Props {
  links: LinksInfo;
}

export default function PolicyPage({ links }: Props) {
  const brand = links.branding_name || "VPN";
  const supportLink = links.support_bot_link;
  const supportLabel = supportLink
    ? supportLink.split("/").pop() || supportLink
    : "поддержка";

  return (
    <LegalLayout title="Политика конфиденциальности">
      <section className="legal-section">
        <h2>1. Собираемые данные</h2>
        <p>
          <strong>1.1. Обязательные данные:</strong>
        </p>
        <ul>
          <li>Telegram User ID</li>
          <li>Имя пользователя Telegram</li>
          <li>Данные оплаты (через платёжные агрегаторы)</li>
        </ul>
        <p>
          <strong>1.2. Технические данные:</strong>
        </p>
        <ul>
          <li>Время подключения</li>
          <li>Тип устройства (без IMEI / серийных номеров)</li>
          <li>Объём трафика (без анализа содержимого)</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>2. Запрет на сбор</h2>
        <p>2.1. Мы никогда не сохраняем:</p>
        <ul>
          <li>Историю посещённых сайтов</li>
          <li>IP-адреса пользователей</li>
          <li>Передаваемый контент (файлы, сообщения)</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>3. Использование данных</h2>
        <p>3.1. Данные используются исключительно для:</p>
        <ul>
          <li>Активации доступа к VPN</li>
          <li>Оказания технической поддержки</li>
          <li>Оповещений о новых тарифах и изменениях в сервисе</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>4. Защита данных</h2>
        <p>
          4.1. Все данные хранятся на зашифрованных серверах в юрисдикциях, не
          требующих хранения логов (Швейцария, Румыния).
        </p>
        <p>
          4.2. Ключи доступа к VPN генерируются автоматически и удаляются при
          отмене подписки.
        </p>
      </section>

      <section className="legal-section">
        <h2>5. Передача третьим лицам</h2>
        <p>5.1. Данные передаются только в следующих случаях:</p>
        <ul>
          <li>Платёжным системам для обработки транзакций</li>
          <li>По официальному запросу уполномоченных органов РФ</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>6. Срок хранения</h2>
        <p>6.1. Ваши данные удаляются:</p>
        <ul>
          <li>Через 30 дней после прекращения подписки</li>
          <li>По вашему запросу через службу поддержки</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>7. Права пользователя</h2>
        <p>Вы имеете право запросить:</p>
        <ul>
          <li>Доступ к вашим данным</li>
          <li>Исправление неточной информации</li>
          <li>Удаление аккаунта и всех связанных данных</li>
        </ul>
        <p>
          Для реализации этих прав обратитесь в поддержку:{" "}
          {supportLink ? (
            <a href={supportLink} target="_blank" rel="noreferrer">
              {supportLabel}
            </a>
          ) : (
            <span>{supportLabel}</span>
          )}
        </p>
      </section>

      <p className="legal-footer-note">
        Используя сервис {brand}, вы подтверждаете согласие с настоящей политикой.
      </p>
    </LegalLayout>
  );
}
