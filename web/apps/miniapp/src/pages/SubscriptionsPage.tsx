import { ArrowLeft, Link2, RefreshCw, ShoppingBag, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Spinner } from "@xray/ui/components/spinner";
import {
  type ManagedSubscription,
  subscriptions as subscriptionsApi,
} from "../api/client";
import SubscriptionCard from "../components/SubscriptionCard";
import { useT } from "../i18n/LocaleContext";

export default function SubscriptionsPage({ refresh }: { refresh: () => void }) {
  const navigate = useNavigate();
  const { t } = useT();
  const [items, setItems] = useState<ManagedSubscription[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = async () => {
    setError(null);
    try {
      setItems((await subscriptionsApi.list()).subscriptions);
    } catch {
      setError(t("subscriptions.loadError"));
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const makePrimary = async (id: number) => {
    setBusy(id);
    try {
      await subscriptionsApi.makePrimary(id);
      await load();
      refresh();
      toast.success(t("subscriptions.primaryChanged"));
    } catch {
      toast.error(t("subscriptions.notFound"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button size="icon" variant="outline" onClick={() => navigate("/")} aria-label={t("common.back")}>
            <ArrowLeft />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-foreground">{t("subscriptions.title")}</h1>
            <p className="text-xs text-muted-foreground">{t("subscriptions.subtitle")}</p>
          </div>
        </div>
        <Button size="icon" variant="ghost" onClick={() => void load()} aria-label={t("home.refreshAria")}>
          <RefreshCw />
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}
      {!items && !error && <div className="spinner-wrap"><Spinner className="h-8 w-8" /></div>}
      {items?.length === 0 && (
        <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          {t("subscriptions.empty")}
        </div>
      )}
      <div className="flex flex-col gap-4">
        {items?.map((subscription) => {
          const unavailable = subscription.status === "unavailable";
          const query = `?subscription_id=${subscription.id}`;
          return (
            <section key={subscription.id} className="space-y-2">
              <div className="flex items-center justify-between gap-2 px-1">
                <div className="min-w-0 truncate text-sm font-semibold text-foreground">
                  {subscription.label || t("subscriptions.fallbackLabel", { id: subscription.rw_id })}
                </div>
                <div className="flex items-center gap-1.5">
                  {subscription.is_primary && <Badge variant="secondary">{t("subscriptions.primary")}</Badge>}
                  <span className="text-[11px] text-muted-foreground">#{subscription.rw_id}</span>
                </div>
              </div>
              <SubscriptionCard sub={{ ...subscription, subscription_id: subscription.id }} />
              {unavailable && (
                <Alert variant="warning"><AlertTitle>{t("subscriptions.unavailable")}</AlertTitle></Alert>
              )}
              <div className="grid grid-cols-2 gap-2">
                {!subscription.is_primary && (
                  <Button variant="outline" disabled={busy === subscription.id} onClick={() => void makePrimary(subscription.id)}>
                    {busy === subscription.id ? <Spinner /> : <Star />} {t("subscriptions.makePrimary")}
                  </Button>
                )}
                <Button variant="outline" disabled={unavailable || !subscription.subscription_url} onClick={() => navigate(`/connect${query}`)}>
                  <Link2 /> {t("subscriptions.connect")}
                </Button>
                <Button className={!subscription.is_primary ? "" : "col-span-2"} onClick={() => navigate(`/buy${query}`)}>
                  <ShoppingBag /> {t("subscriptions.renew")}
                </Button>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
