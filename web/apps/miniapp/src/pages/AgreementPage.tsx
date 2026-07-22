import LegalLayout from "../components/LegalLayout";
import { LinksInfo } from "../api/client";
import { useT } from "../i18n/LocaleContext";

interface Props {
  links: LinksInfo;
}

export default function AgreementPage({ links }: Props) {
  const { t } = useT();
  const brand = links.branding_name || t("legal.brandFallback");
  const supportLink = links.support_bot_link;
  const supportLabel = supportLink
    ? supportLink.split("/").pop() || supportLink
    : t("legal.supportFallback");

  return (
    <LegalLayout title={t("legal.agreement.title")}>
      <section className="legal-section">
        <h2>{t("legal.agreement.s1.title")}</h2>
        <p>{t("legal.agreement.s1.p1", { brand })}</p>
        <p>{t("legal.agreement.s1.p2")}</p>
      </section>

      <section className="legal-section">
        <h2>{t("legal.agreement.s2.title")}</h2>
        <p>{t("legal.agreement.s2.p1")}</p>
        <ul>
          <li>{t("legal.agreement.s2.i1")}</li>
          <li>{t("legal.agreement.s2.i2")}</li>
          <li>{t("legal.agreement.s2.i3")}</li>
        </ul>
        <p>
          <strong>{t("legal.agreement.s2.p2")}</strong>
        </p>
        <ul>
          <li>{t("legal.agreement.s2.i4")}</li>
          <li>{t("legal.agreement.s2.i5")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.agreement.s3.title")}</h2>
        <p>{t("legal.agreement.s3.p1")}</p>
        <p>{t("legal.agreement.s3.p2")}</p>
      </section>

      <section className="legal-section">
        <h2>{t("legal.agreement.s4.title")}</h2>
        <p>{t("legal.agreement.s4.p1")}</p>
        <p>{t("legal.agreement.s4.p2")}</p>
        <ul>
          <li>{t("legal.agreement.s4.i1")}</li>
          <li>{t("legal.agreement.s4.i2")}</li>
          <li>{t("legal.agreement.s4.i3")}</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>{t("legal.agreement.s5.title")}</h2>
        <p>{t("legal.agreement.s5.p1")}</p>
        <p>{t("legal.agreement.s5.p2")}</p>
      </section>

      <section className="legal-section">
        <h2>{t("legal.agreement.s6.title")}</h2>
        <p>
          {t("legal.agreement.s6.p1")}{" "}
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
        {t("legal.agreement.callout", { brand })}
      </div>
    </LegalLayout>
  );
}
