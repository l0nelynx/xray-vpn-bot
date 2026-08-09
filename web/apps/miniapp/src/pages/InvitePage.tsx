import { ArrowLeft, Copy, Gift, Share2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Spinner } from "@xray/ui/components/spinner";
import { ReferralState, referral as referralApi } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { formatPoints, POINTS_ICON } from "../points";
import { copyToClipboard, hapticImpact, shareToTelegram } from "../tg/webapp";

export default function InvitePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useT();
  const [state, setState] = useState<ReferralState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    referralApi
      .getState()
      .then(setState)
      .catch((e) => setError(e?.detail || String(e)));
  }, []);

  const inviteText = state
    ? t("invite.shareText", { creditGrant: formatPoints(state.credit_grant) })
    : "";
  const requestedReturnTo = (location.state as { returnTo?: unknown } | null)?.returnTo;
  const returnTo = typeof requestedReturnTo === "string" && requestedReturnTo.startsWith("/") && !requestedReturnTo.startsWith("//")
    ? requestedReturnTo
    : "/";

  const handleCopy = async () => {
    if (!state) return;
    hapticImpact("light");
    const ok = await copyToClipboard(state.code);
    if (ok) toast.success(t("invite.toast.copied"));
    else toast.error(t("invite.toast.copyFailed"));
  };

  const handleShare = () => {
    if (!state?.deeplink) return;
    hapticImpact("medium");
    shareToTelegram(state.deeplink, inviteText);
  };

  return (
    <div className="page">
      <div className="page-header">
        <Button variant="ghost" size="icon" onClick={() => navigate(returnTo, { replace: true })} aria-label={t("invite.backAria")}>
          <ArrowLeft />
        </Button>
        <div className="text-xl font-bold text-foreground">{t("invite.title")}</div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}

      {!state && !error && (
        <div className="spinner-wrap">
          <Spinner />
        </div>
      )}

      {state && (
        <div className="flex flex-col gap-4 w-full">
          <Card className="border-primary/40">
            <CardContent className="p-4 flex flex-col gap-2">
              <span className="text-muted-foreground flex items-center gap-1.5">
                <Gift className="w-3.5 h-3.5" /> {t("invite.yourCode")}
              </span>
              <div className="m-0 text-center text-2xl font-bold text-foreground tracking-widest">
                {state.code}
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-2.5 w-full">
            <Button variant="outline" size="lg" className="w-full" onClick={handleCopy}>
              <Copy />
              {t("invite.copyCode")}
            </Button>
            <Button size="lg" className="w-full" onClick={handleShare} disabled={!state.deeplink}>
              <Share2 />
              {t("invite.share")}
            </Button>
          </div>

          <Card>
            <CardContent className="p-4 flex justify-around gap-4">
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t("invite.stat.purchased")}</div>
                <div className="text-xl font-bold text-foreground">
                  {t("invite.daysShort", { count: state.days_purchased })}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t("invite.stat.rewarded")}</div>
                <div className="text-xl font-bold text-foreground">
                  {state.points_rewarded} {POINTS_ICON}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <p className="mb-2 mt-0 text-foreground">
                <b>{t("invite.howTitle")}</b>
              </p>
              <p className="text-muted-foreground mb-0">
                {t("invite.howBody", {
                  creditGrant: formatPoints(state.credit_grant),
                  per30: formatPoints(state.points_reward_per_30),
                  cap: formatPoints(state.reward_cap_points),
                })}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
