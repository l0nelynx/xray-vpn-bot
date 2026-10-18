import { useEffect, useRef, useState } from "react";
import { Bell, Check } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { remnawaveAvailability, type RemnawaveAvailability } from "../api/client";
import { useT } from "../i18n/LocaleContext";

export default function RemnawaveMaintenance({ onRecovered, subscriptionStatus }: {
  onRecovered: () => void;
  subscriptionStatus?: string | null;
}) {
  const { t, locale } = useT();
  const [status, setStatus] = useState<RemnawaveAvailability | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const recovered = useRef(onRecovered);
  recovered.current = onRecovered;
  const previousUnavailable = useRef(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const next = await remnawaveAvailability.get();
        if (!active) return;
        if (previousUnavailable.current && !next.unavailable) recovered.current();
        previousUnavailable.current = next.unavailable;
        setStatus(next);
      } catch {
        // Preserve the last known status during a temporary API/network failure.
      } finally {
        if (active) timer = setTimeout(() => void load(), 15_000);
      }
    };
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [subscriptionStatus]);

  const subscribe = async () => {
    setBusy(true);
    setFailed(false);
    try {
      const next = await remnawaveAvailability.subscribe(locale);
      setStatus(next);
      if (!next.unavailable) recovered.current();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  if (!status?.unavailable) return null;

  return (
    <div className="mx-auto w-full max-w-[480px] px-4 pt-4">
      <Alert variant="warning">
        <AlertTitle>{t("maintenance.title")}</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{t("subscriptions.unavailable")}</p>
          {status.subscribed ? (
            <p className="flex items-center gap-2" role="status"><Check className="h-4 w-4" />{t("maintenance.subscribed")}</p>
          ) : (
            <Button className="h-auto min-h-9 w-full whitespace-normal py-2" variant="outline" disabled={busy} onClick={() => void subscribe()}>
              <Bell className="h-4 w-4" />{t(busy ? "maintenance.subscribing" : "maintenance.notify")}
            </Button>
          )}
          {failed && <p role="status">{t("maintenance.subscribeError")}</p>}
        </AlertDescription>
      </Alert>
    </div>
  );
}
