import { useEffect, useState } from "react";
import { Spinner } from "@xray/ui/components/spinner";
import LegalLayout from "../components/LegalLayout";
import { ReferralState, referral as referralApi } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { formatPoints } from "../points";

export default function ReferralRulesPage() {
  const { t } = useT();
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
      <LegalLayout title={t("referralRules.titleLoading")}>
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <Spinner className="h-8 w-8" />
        </div>
      </LegalLayout>
    );
  }

  return (
    <LegalLayout title={t("referralRules.title")}>
      <section className="legal-section">
        <h2>{t("referralRules.s1.title")}</h2>
        <ul>
          <li>{t("referralRules.s1.i1")}</li>
          <li>
            {t("referralRules.s1.i2", {
              creditGrant: formatPoints(referralState?.credit_grant ?? 0),
            })}
          </li>
          <li>{t("referralRules.s1.i3")}</li>
          <li>{t("referralRules.s1.i4")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("referralRules.s2.title")}</h2>
        <ul>
          <li>
            {t("referralRules.s2.i1", {
              per30: formatPoints(referralState?.points_reward_per_30 ?? 0),
            })}
          </li>
          <li>
            {t("referralRules.s2.i2", {
              cap: formatPoints(referralState?.reward_cap_points ?? 0),
            })}
          </li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("referralRules.s3.title")}</h2>
        <ul>
          <li>{t("referralRules.s3.i1")}</li>
          <li>{t("referralRules.s3.i2")}</li>
          <li>{t("referralRules.s3.i3")}</li>
        </ul>
      </section>
    </LegalLayout>
  );
}
