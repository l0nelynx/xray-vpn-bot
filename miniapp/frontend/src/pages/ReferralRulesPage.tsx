import { useEffect, useState } from "react";
import { Typography, Spin } from "antd";
import LegalLayout from "../components/LegalLayout";
import { ReferralState, referral as referralApi } from "../api/client";

export default function ReferralRulesPage() {
  const [referralState, setReferralState] = useState<ReferralState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    referralApi
      .getState()
      .then(setReferralState)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <LegalLayout title="Правила программы">
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <Spin size="large" />
        </div>
      </LegalLayout>
    );
  }

  return (
    <LegalLayout title="Правила реферальной программы">
      <section className="legal-section">
        <h2>Реферальные промокоды</h2>
        <ul>
          <li>
            У каждого пользователя есть личный промокод — поделитесь им с
            друзьями.
          </li>
          <li>
            Друг получает скидку{" "}
            <strong>{referralState?.discount_percent ?? 0}%</strong> на первую покупку.
          </li>
          <li>
            Реферальный промокод доступен только новым пользователям — у кого
            ещё не было покупок.
          </li>
          <li>Активировать реферальный промокод можно только один раз.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>Бонусы за приглашения</h2>
        <ul>
          <li>
            За каждые 30 дней, купленных по вашему коду, вы получаете{" "}
            <strong>{referralState?.days_reward_per_30 ?? 0}</strong> бонусных дней.
          </li>
          <li>
            Всего можно получить до{" "}
            <strong>{referralState?.reward_cap_days ?? 0}</strong> бонусных дней.
          </li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>Обычные промокоды</h2>
        <ul>
          <li>Доступны всем пользователям.</li>
          <li>Каждый конкретный промокод можно использовать только один раз.</li>
          <li>
            Одновременно может быть активен только один промокод — используйте
            его при оплате перед активацией следующего.
          </li>
        </ul>
      </section>
    </LegalLayout>
  );
}
