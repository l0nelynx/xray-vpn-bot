import LegalLayout from "../components/LegalLayout";
import { LinksInfo } from "../api/client";
import { useT } from "../i18n/LocaleContext";

interface Props {
  links: LinksInfo;
}

export default function PolicyPage({ links }: Props) {
  const { t } = useT();
  const brand = links.branding_name || t("legal.brandFallback");
  const supportLink = links.support_bot_link;
  const supportLabel = supportLink
    ? supportLink.split("/").pop() || supportLink
    : t("legal.supportFallback");

  return (
    <LegalLayout title={t("legal.policy.title")}>
      <section className="legal-section">
        <h2>{t("legal.policy.s1.title")}</h2>
        <p>
          <strong>{t("legal.policy.s1.p1")}</strong>
        </p>
        <ul>
          <li>{t("legal.policy.s1.i1")}</li>
          <li>{t("legal.policy.s1.i2")}</li>
          <li>{t("legal.policy.s1.i3")}</li>
        </ul>
        <p>
          <strong>{t("legal.policy.s1.p2")}</strong>
        </p>
        <ul>
          <li>{t("legal.policy.s1.i4")}</li>
          <li>{t("legal.policy.s1.i5")}</li>
          <li>{t("legal.policy.s1.i6")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.policy.s2.title")}</h2>
        <p>{t("legal.policy.s2.p1")}</p>
        <ul>
          <li>{t("legal.policy.s2.i1")}</li>
          <li>{t("legal.policy.s2.i2")}</li>
          <li>{t("legal.policy.s2.i3")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.policy.s3.title")}</h2>
        <p>{t("legal.policy.s3.p1")}</p>
        <ul>
          <li>{t("legal.policy.s3.i1")}</li>
          <li>{t("legal.policy.s3.i2")}</li>
          <li>{t("legal.policy.s3.i3")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.policy.s4.title")}</h2>
        <p>{t("legal.policy.s4.p1")}</p>
        <p>{t("legal.policy.s4.p2")}</p>
      </section>

      <section className="legal-section">
        <h2>{t("legal.policy.s5.title")}</h2>
        <p>{t("legal.policy.s5.p1")}</p>
        <ul>
          <li>{t("legal.policy.s5.i1")}</li>
          <li>{t("legal.policy.s5.i2")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.policy.s6.title")}</h2>
        <p>{t("legal.policy.s6.p1")}</p>
        <ul>
          <li>{t("legal.policy.s6.i1")}</li>
          <li>{t("legal.policy.s6.i2")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.policy.s7.title")}</h2>
        <p>{t("legal.policy.s7.p1")}</p>
        <ul>
          <li>{t("legal.policy.s7.i1")}</li>
          <li>{t("legal.policy.s7.i2")}</li>
          <li>{t("legal.policy.s7.i3")}</li>
        </ul>
        <p>
          {t("legal.policy.s7.p2")}{" "}
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
        {t("legal.policy.footer", { brand })}
      </p>
    </LegalLayout>
  );
}
