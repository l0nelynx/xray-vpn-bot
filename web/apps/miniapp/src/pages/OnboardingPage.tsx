import { ArrowRight, CircleHelp, Download, KeyRound, Laptop, Link2, ListPlus, Power, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Button } from "@xray/ui/components/button";
import { me as meApi, type MeResponse } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { trackUx } from "../ux";

export const ONBOARDING_VERSION = 1;

const LESSONS = [
  { icon: KeyRound, eyebrow: "onboarding.access.eyebrow", title: "onboarding.access.title", body: "onboarding.access.body" },
  { icon: Link2, eyebrow: "onboarding.connect.eyebrow", title: "onboarding.connect.title", body: "onboarding.connect.body" },
  { icon: Laptop, eyebrow: "onboarding.help.eyebrow", title: "onboarding.help.title", body: "onboarding.help.body" },
] as const;

export default function OnboardingPage({
  me,
  reload,
}: {
  me: MeResponse;
  reload: () => Promise<MeResponse | null>;
}) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useT();
  const replay = searchParams.get("replay") === "1";
  const initial = Math.min(3, Math.max(0, Number(searchParams.get("step") || 0)));
  const [step, setStep] = useState(initial);
  const [busy, setBusy] = useState(false);
  const tracked = useRef(false);

  useEffect(() => {
    if (tracked.current) return;
    tracked.current = true;
    trackUx({ name: "onboarding_started", onboarding_version: ONBOARDING_VERSION, source: replay ? "help" : "gate" });
  }, [replay]);

  function go(next: number) {
    setStep(next);
    setSearchParams({ ...(replay ? { replay: "1" } : {}), step: String(next) }, { replace: true });
  }

  async function finish(outcome: "completed" | "skipped") {
    if (busy) return;
    setBusy(true);
    try {
      await meApi.setOnboarding(ONBOARDING_VERSION, outcome);
      trackUx({ name: outcome === "completed" ? "onboarding_completed" : "onboarding_skipped", onboarding_version: ONBOARDING_VERSION });
      const fresh = await reload();
      if (replay) {
        navigate("/support", { replace: true });
      } else if (fresh?.subscription?.status === "active" && fresh.subscription.connection_state === "never_connected") {
        const query = fresh.subscription.subscription_id ? `?subscription_id=${fresh.subscription.subscription_id}` : "";
        navigate(`/connect${query}`, { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } finally {
      setBusy(false);
    }
  }

  if (step === 0) {
    return (
      <div className="onboarding-shell">
        <button className="onboarding-skip" onClick={() => void finish("skipped")}>{t("onboarding.skip")}</button>
        <div className="onboarding-hero onboarding-identity">
          <div className="onboarding-glyph"><ShieldCheck /></div>
          <span className="onboarding-eyebrow">{t("onboarding.identity.eyebrow")}</span>
          <h1>{t("onboarding.identity.title")}</h1>
          <p>{t("onboarding.identity.body")}</p>
        </div>
        <div className="onboarding-actions">
          {!me.user?.has_email && (
            <Button size="lg" className="w-full" onClick={() => navigate(`/account/link?returnTo=${encodeURIComponent("/onboarding?step=1")}`)}>
              {t("onboarding.identity.email")}<ArrowRight />
            </Button>
          )}
          <Button size="lg" variant={me.user?.has_email ? "default" : "outline"} className="w-full" onClick={() => go(1)}>
            {me.user?.has_email ? t("onboarding.identity.continueLinked") : t("onboarding.identity.telegram")}
          </Button>
          <span className="onboarding-hint">{me.user?.has_email ? me.user.email : t("onboarding.identity.hint")}</span>
        </div>
      </div>
    );
  }

  const lesson = LESSONS[step - 1];
  const Icon = lesson.icon;
  return (
    <div className="onboarding-shell">
      <button className="onboarding-skip" onClick={() => void finish("skipped")}>{t("onboarding.skip")}</button>
      <div className="onboarding-progress" aria-label={t("onboarding.progress", { current: step, total: 3 })}>
        {LESSONS.map((_, index) => <span key={index} className={index < step ? "active" : ""} />)}
      </div>
      <div className="onboarding-hero">
        <div className="onboarding-glyph"><Icon /></div>
        <span className="onboarding-eyebrow">{t(lesson.eyebrow)}</span>
        <h1>{t(lesson.title)}</h1>
        <p>{t(lesson.body)}</p>
      </div>
      {step === 2 && (
        <div className="connection-rail compact" aria-hidden="true">
          <span className="done"><Download /></span><i /><span className="active"><ListPlus /></span><i /><span><Power /></span>
        </div>
      )}
      {step === 3 && <div className="onboarding-help-pair"><Laptop /><CircleHelp /></div>}
      <div className="onboarding-actions">
        <Button size="lg" className="w-full" disabled={busy} onClick={() => step < 3 ? go(step + 1) : void finish("completed")}>
          {step < 3 ? t("onboarding.next") : t("onboarding.finish")}<ArrowRight />
        </Button>
      </div>
    </div>
  );
}
