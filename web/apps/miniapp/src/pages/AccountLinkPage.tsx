import { ArrowLeft, Link2, Lock, Mail, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { ApiError, linkEmail, type MeResponse } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { trackUx } from "../ux";

function errorCode(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const detail = error.detail as unknown;
  if (detail && typeof detail === "object" && "code" in detail) {
    return String((detail as { code: unknown }).code);
  }
  return null;
}

export default function AccountLinkPage({
  hasEmail,
  email,
  reload,
}: {
  hasEmail: boolean;
  email: string | null;
  reload: () => Promise<MeResponse | null>;
}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useT();
  const [loginEmail, setLoginEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [supportCta, setSupportCta] = useState(false);
  const returnTo = searchParams.get("returnTo") || "/";

  async function submit() {
    if (!loginEmail.trim() || !password || busy) return;
    setBusy(true);
    setError(null);
    setSupportCta(false);
    trackUx({ name: "email_link_started", source: "account_link" });
    try {
      await linkEmail.link(loginEmail.trim().toLowerCase(), password);
      trackUx({ name: "email_link_succeeded", source: "account_link" });
      await reload();
      navigate(returnTo, { replace: true });
    } catch (reason) {
      const code = errorCode(reason);
      trackUx({ name: "email_link_failed", source: "account_link", outcome: code || "unknown" });
      if (code === "invalid_credentials") setError(t("accountLink.error.credentials"));
      else if (code === "telegram_conflict") {
        setError(t("accountLink.error.conflict"));
        setSupportCta(true);
      } else if (code === "already_has_email") setError(t("accountLink.error.hasEmail"));
      else if (code === "banned") setError(t("accountLink.error.banned"));
      else setError(t("accountLink.error.generic"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page account-link-page">
      <Button size="icon" variant="ghost" className="stack-back" onClick={() => navigate(-1)} aria-label={t("common.back")}>
        <ArrowLeft />
      </Button>

      <div className="account-link-mark"><Link2 /></div>
      <h1>{t("accountLink.title")}</h1>
      <p className="page-lead">{t("accountLink.body")}</p>

      {hasEmail ? (
        <div className="quiet-panel account-linked">
          <ShieldCheck />
          <div>
            <strong>{t("accountLink.alreadyTitle")}</strong>
            <span>{email}</span>
          </div>
        </div>
      ) : (
        <form onSubmit={(event) => { event.preventDefault(); void submit(); }} className="account-link-form">
          <label htmlFor="account-email">{t("accountLink.email")}</label>
          <div className="field-with-icon">
            <Mail />
            <Input id="account-email" type="email" autoComplete="email" value={loginEmail} onChange={(event) => setLoginEmail(event.target.value)} />
          </div>
          <label htmlFor="account-password">{t("accountLink.password")}</label>
          <div className="field-with-icon">
            <Lock />
            <Input id="account-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertTitle>{t("accountLink.error.title")}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button size="lg" type="submit" className="w-full" disabled={busy || !loginEmail.trim() || !password}>
            {busy ? t("accountLink.submitting") : t("accountLink.submit")}
          </Button>
          {supportCta && <Button type="button" variant="outline" className="w-full" onClick={() => navigate("/support/new")}>{t("accountLink.support")}</Button>}
        </form>
      )}
      <p className="privacy-note"><ShieldCheck />{t("accountLink.safety")}</p>
    </div>
  );
}
