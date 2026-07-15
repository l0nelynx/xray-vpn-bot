import { useEffect, useState } from "react";
import { Typography, Spin } from "antd";
import LegalLayout from "../components/LegalLayout";
import { ReferralState, referral as referralApi } from "../api/client";
import { formatPoints } from "../points";

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
            Друг получает{" "}
            <strong>{formatPoints(referralState?.credit_grant ?? 0)}</strong> при активации кода.
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
            За каждые 30 дней покупок по вашему коду вы получаете{" "}
            <strong>{formatPoints(referralState?.points_reward_per_30 ?? 0)}</strong>.
          </li>
          <li>
            Всего можно получить до{" "}
            <strong>{formatPoints(referralState?.reward_cap_points ?? 0)}</strong>.
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
