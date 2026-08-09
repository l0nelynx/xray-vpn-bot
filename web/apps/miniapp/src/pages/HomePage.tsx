import {
  ArrowRight,
  ChevronRight,
  Gift,
  Laptop,
  Link as LinkIcon,
  LogIn,
  RefreshCw,
  Settings,
  UserPlus,
  Wifi,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@xray/ui/components/dialog";
import { Input } from "@xray/ui/components/input";
import { toast } from "sonner";
import { promo as promoApi, type MeResponse, type PromoState } from "../api/client";
import SubscriptionCard from "../components/SubscriptionCard";
import { useT } from "../i18n/LocaleContext";
import { formatPoints, POINTS_ICON } from "../points";
import { showAlert } from "../tg/webapp";

interface Props {
  me: MeResponse;
  reload: () => Promise<MeResponse | null>;
  refresh: () => Promise<MeResponse | null>;
}

export default function HomePage({ me, reload, refresh }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useT();
  const sub = me.subscription;
  const username = me.user?.username;
  const targetQuery = sub?.subscription_id ? `?subscription_id=${sub.subscription_id}` : "";
  const isActive = sub?.status === "active";
  const hasConnected = sub?.connection_state === "connected";
  const [promoState, setPromoState] = useState<PromoState | null>(null);
  const [promoOpen, setPromoOpen] = useState(false);
  const [promoCode, setPromoCode] = useState("");
  const [activatingPromo, setActivatingPromo] = useState(false);

  useEffect(() => {
    void promoApi.getState().then(setPromoState).catch(() => {});
  }, []);

  const lastReloadKey = useRef<string>("");
  useEffect(() => {
    const key = location.key || "default";
    if (lastReloadKey.current !== key) {
      lastReloadKey.current = key;
      void refresh();
    }
  }, [location.key, refresh]);

  const activatePromo = async () => {
    const code = promoCode.trim().toUpperCase();
    if (!code || activatingPromo) return;
    setActivatingPromo(true);
    try {
      const result = await promoApi.activate(code);
      setPromoState((current) => ({
        balance: result.balance,
        last_promo_code: result.promo_code,
        default_credit_grant: current?.default_credit_grant ?? 0,
      }));
      setPromoCode("");
      setPromoOpen(false);
      toast.success(t("settings.promo.toastSuccess", {
        grant: formatPoints(result.credit_grant),
        balance: formatPoints(result.balance),
      }));
    } catch (reason) {
      showAlert(reason instanceof Error ? reason.message : t("settings.promo.errorFallback"));
    } finally {
      setActivatingPromo(false);
    }
  };

  return (
    <div className="page home-page">
      <div className="home-header">
        <div className="home-identity">
          <button className="home-username" onClick={() => navigate("/settings")} aria-label={t("settings.title")}>
            {username ? `@${username}` : t("home.titleFallback")}
          </button>
          <div className="text-[13px] text-muted-foreground mt-0.5">{t("home.subtitle")}</div>
        </div>
        <div className="home-header__actions">
          <button
            className="home-promo-trigger"
            onClick={() => setPromoOpen(true)}
            aria-label={`${t("home.activatePromo")}: ${formatPoints(promoState?.balance ?? 0)}`}
          >
            <Gift />
            <span className="home-promo-balance">{formatPoints(promoState?.balance ?? 0)}</span>
          </button>
          <Button className="refresh-fab home-refresh-button" size="icon" variant="outline" onClick={() => void reload()} aria-label={t("home.refreshAria")}><RefreshCw /></Button>
          <Button className="refresh-fab home-settings-button" size="icon" variant="outline" onClick={() => navigate("/settings")} aria-label={t("settings.title")}><Settings /></Button>
        </div>
      </div>

      {sub ? (
        <div className="flex flex-col gap-2.5 w-full">
          <SubscriptionCard
            sub={sub}
            compact
            subscriptionsCount={me.subscriptions_count}
            onManageSubscriptions={() => navigate("/subscriptions")}
          />

          <div className="home-utility-grid">
            <button className="home-utility" onClick={() => navigate("/devices")}>
              <Laptop />
              <span><small>{t("home.devicesHint")}</small><strong>{t("home.devicesCountShort", { count: sub.devices_count })}</strong></span>
            </button>
            <button className="home-utility" onClick={() => navigate("/invite", { state: { returnTo: "/" } })}>
              <UserPlus />
              <span><small>{t("home.inviteHint")}</small><strong>{t("settings.inviteFriends")}</strong></span>
            </button>
          </div>

          <Button size="lg" className="w-full home-primary-cta" onClick={() => navigate(isActive ? `/connect${targetQuery}` : `/buy${targetQuery}`)}>
            {isActive ? <LinkIcon /> : <ArrowRight />}
            {isActive
              ? (hasConnected ? t("home.connectAnother") : t("home.setupVpn"))
              : t("home.resume")}
          </Button>

          <button className="home-row" onClick={() => navigate("/free/telemt")}>
            <span className="home-row__icon"><Wifi /></span>
            <span><strong>{t("home.telegramProxy")}</strong><small>{t("home.telegramProxyBody")}</small></span>
            <ChevronRight />
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5 w-full">
          <Card className="empty-access-card">
            <CardContent className="p-7 px-5 text-center">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-3.5"><Wifi className="text-foreground w-6 h-6" /></div>
              <div className="text-[17px] font-semibold text-foreground mb-2">{t("home.emptyTitle")}</div>
              <div className="text-sm text-muted-foreground leading-relaxed">{t("home.emptyBody")}</div>
            </CardContent>
          </Card>

          <Button size="lg" className="w-full" onClick={() => navigate("/buy")}>{t("home.buy")}</Button>

          <div className="home-utility-grid">
            <button className="home-utility" onClick={() => navigate("/devices")}>
              <Laptop />
              <span><small>{t("home.devicesHint")}</small><strong>{t("home.devicesCountShort", { count: 0 })}</strong></span>
            </button>
            <button className="home-utility" onClick={() => navigate("/invite", { state: { returnTo: "/" } })}>
              <UserPlus />
              <span><small>{t("home.inviteHint")}</small><strong>{t("settings.inviteFriends")}</strong></span>
            </button>
          </div>

          {!me.user?.has_email && (
            <button className="email-recovery-card" onClick={() => navigate("/account/link?returnTo=%2F")}>
              <LogIn />
              <span><strong>{t("home.existingAccount")}</strong><small>{t("home.existingAccountBody")}</small></span>
              <ChevronRight />
            </button>
          )}

          <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/free/vpn")}>{t("home.tryFree")}</Button>
          <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/free/telemt")}><Wifi />{t("home.telegramProxy")}</Button>
        </div>
      )}

      <Dialog open={promoOpen} onOpenChange={(open: boolean) => { setPromoOpen(open); if (!open) setPromoCode(""); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t("settings.promo.modalTitle")}</DialogTitle></DialogHeader>
          <div className="flex flex-col gap-3 pt-1">
            <p className="m-0 text-sm text-muted-foreground">{t("settings.promo.modalBody", { icon: POINTS_ICON })}</p>
            <Input
              value={promoCode}
              onChange={(event) => setPromoCode(event.target.value.toUpperCase())}
              onKeyDown={(event) => event.key === "Enter" && void activatePromo()}
              placeholder={t("settings.promo.placeholder")}
              maxLength={20}
              autoFocus
            />
            <Button size="lg" disabled={activatingPromo || !promoCode.trim()} onClick={() => void activatePromo()}>
              {activatingPromo ? t("settings.promo.applying") : t("settings.promo.apply")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
