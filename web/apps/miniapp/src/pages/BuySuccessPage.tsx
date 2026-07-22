import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { Alert, AlertTitle, AlertDescription } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { api, MeResponse } from "../api/client";
import { hapticImpact, openLink } from "../tg/webapp";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000;

interface LocationState {
  paymentUrl?: string;
  baselineExpireIso?: string | null;
  baselineDaysLeft?: number;
}

export default function BuySuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as LocationState;

  const [me, setMe] = useState<MeResponse | null>(null);
  const [done, setDone] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const startedAt = useRef<number>(Date.now());

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const fresh = await api.get<MeResponse>("/me");
        if (cancelled) return;
        setMe(fresh);
        const sub = fresh.subscription;
        const updated =
          sub != null &&
          (sub.expire_iso !== (state.baselineExpireIso ?? null) ||
            sub.days_left !== (state.baselineDaysLeft ?? 0));
        if (updated && sub?.subscription_url) {
          setDone(true);
          hapticImpact("medium");
          return;
        }
      } catch {
        /* keep polling */
      }
      if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
        setTimedOut(true);
        return;
      }
      timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [state.baselineDaysLeft, state.baselineExpireIso]);

  const subUrl = me?.subscription?.subscription_url;

  if (done && subUrl) {
    return (
      <div className="page">
        <Card className="text-center">
          <CardContent className="p-6">
            <CheckCircle2 className="w-14 h-14 text-emerald-500 mx-auto" />
            <div className="text-xl font-bold text-foreground mt-4">
              Оплата получена
            </div>
            <p className="text-muted-foreground mt-2 mb-5">
              Подписка активирована. Откройте ссылку, чтобы подключиться:
            </p>
            <div className="flex flex-col gap-3 w-full">
              <Button size="lg" className="w-full" onClick={() => openLink(subUrl)}>
                Открыть подписку
              </Button>
              <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/", { replace: true })}>
                На главную
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (timedOut) {
    return (
      <div className="page">
        <Alert variant="warning">
          <AlertTitle>Подтверждение оплаты заняло больше времени, чем ожидалось</AlertTitle>
          <AlertDescription>
            Если деньги уже списаны — подписка появится в течение нескольких минут. Откройте главную и нажмите «Обновить».
          </AlertDescription>
        </Alert>
        <div className="mt-4">
          <Button className="w-full" size="lg" onClick={() => navigate("/", { replace: true })}>
            На главную
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Card className="text-center">
        <CardContent className="p-6">
          <Loader2 className="animate-spin w-12 h-12 mx-auto" />
          <div className="text-lg font-bold text-foreground mt-4">
            Ждём подтверждение оплаты…
          </div>
          <p className={`text-muted-foreground mt-2 ${state.paymentUrl ? "mb-4" : "mb-0"}`}>
            Это занимает обычно несколько секунд. Не закрывайте окно.
          </p>
          {state.paymentUrl && (
            <Button variant="outline" className="w-full" onClick={() => openLink(state.paymentUrl!)}>
              Открыть страницу оплаты ещё раз
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
