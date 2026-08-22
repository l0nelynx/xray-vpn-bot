import { AlertCircle, CheckCircle2, Clock3, Loader2, RotateCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { api, payments, type MeResponse, type PaymentState } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { hapticImpact, openLink } from "../tg/webapp";
import { trackUx } from "../ux";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000;

interface LocationState { paymentUrl?: string }

export default function BuySuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { t } = useT();
  const transactionId = searchParams.get("transaction_id") || "";
  const requestedSubscriptionId = Number(searchParams.get("subscription_id") || 0) || null;
  const paymentUrl = ((location.state ?? {}) as LocationState).paymentUrl;
  const previewTimeout = import.meta.env.VITE_MOCK_API === "1" && searchParams.get("preview_timeout") === "1";
  const holdSuccess = import.meta.env.VITE_MOCK_API === "1" && searchParams.get("preview_success") === "1";
  const [state, setState] = useState<PaymentState | "loading" | "invalid">(transactionId ? "loading" : "invalid");
  const [timedOut, setTimedOut] = useState(false);
  const [checking, setChecking] = useState(false);
  const startedAt = useRef(Date.now());
  const lastTracked = useRef<string>("");

  const check = useCallback(async () => {
    if (!transactionId) return null;
    try {
      const result = await payments.getTransaction(transactionId);
      setState(result.state);
      if (lastTracked.current !== result.state) {
        lastTracked.current = result.state;
        const names = {
          awaiting_payment: "payment_awaiting",
          processing: "payment_processing",
          succeeded: "payment_succeeded",
          failed: "payment_failed",
        } as const;
        trackUx({ name: names[result.state], transaction_id: transactionId, subscription_id: requestedSubscriptionId || undefined });
      }
      return result.state;
    } catch {
      setState("invalid");
      return null;
    }
  }, [requestedSubscriptionId, transactionId]);

  useEffect(() => {
    if (!transactionId) return;
    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      const next = await check();
      if (cancelled || next === "succeeded" || next === "failed") return;
      if (previewTimeout || Date.now() - startedAt.current >= POLL_TIMEOUT_MS) {
        setTimedOut(true);
        return;
      }
      timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };
    void poll();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [check, previewTimeout, transactionId]);

  useEffect(() => {
    if (state !== "succeeded" || holdSuccess) return;
    hapticImpact("medium");
    const timer = window.setTimeout(async () => {
      const fresh = await api.get<MeResponse>("/me").catch(() => null);
      const subscriptionId = requestedSubscriptionId || fresh?.subscription?.subscription_id || null;
      const query = new URLSearchParams({ source: "purchase" });
      if (subscriptionId) query.set("subscription_id", String(subscriptionId));
      navigate(`/connect?${query}`, { replace: true });
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [holdSuccess, navigate, requestedSubscriptionId, state]);

  async function manualCheck() {
    setChecking(true);
    setTimedOut(false);
    startedAt.current = Date.now();
    await check();
    setChecking(false);
  }

  if (state === "invalid") {
    return (
      <div className="page payment-state-page">
        <Alert variant="destructive"><AlertTitle>{t("buySuccess.invalidTitle")}</AlertTitle><AlertDescription>{t("buySuccess.invalidBody")}</AlertDescription></Alert>
        <Button className="w-full mt-4" onClick={() => navigate("/buy", { replace: true })}>{t("buySuccess.tryAgain")}</Button>
      </div>
    );
  }

  if (state === "failed") {
    return (
      <div className="page payment-state-page">
        <div className="payment-state-icon failed"><AlertCircle /></div>
        <h1>{t("buySuccess.failedTitle")}</h1><p>{t("buySuccess.failedBody")}</p>
        <Button className="w-full" onClick={() => navigate("/buy", { replace: true })}>{t("buySuccess.tryAgain")}</Button>
        <Button variant="outline" className="w-full" onClick={() => navigate("/support/new")}>{t("buySuccess.support")}</Button>
      </div>
    );
  }

  if (state === "succeeded") {
    return (
      <div className="page payment-state-page">
        <div className="payment-state-icon success"><CheckCircle2 /></div>
        <h1>{t("buySuccess.paidTitle")}</h1><p>{t("buySuccess.redirectConnect")}</p>
        <Loader2 className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="page payment-state-page">
      <div className="payment-state-icon waiting">{state === "processing" ? <Clock3 /> : <Loader2 className="animate-spin" />}</div>
      <h1>{state === "processing" ? t("buySuccess.processingTitle") : t("buySuccess.waitingTitle")}</h1>
      <p>{state === "processing" ? t("buySuccess.processingBody") : t("buySuccess.waitingBody")}</p>
      {timedOut && <Alert variant="warning"><AlertTitle>{t("buySuccess.timeoutTitle")}</AlertTitle><AlertDescription>{t("buySuccess.timeoutBodyNew")}</AlertDescription></Alert>}
      <Button variant="outline" className="w-full" disabled={checking} onClick={() => void manualCheck()}><RotateCw className={checking ? "animate-spin" : ""} />{t("buySuccess.checkAgain")}</Button>
      {paymentUrl && state === "awaiting_payment" && <Button variant="ghost" className="w-full" onClick={() => openLink(paymentUrl)}>{t("buySuccess.reopenPayment")}</Button>}
      {timedOut && <Button variant="ghost" className="w-full" onClick={() => navigate("/support/new")}>{t("buySuccess.support")}</Button>}
    </div>
  );
}
