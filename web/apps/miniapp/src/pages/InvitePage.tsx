import { ArrowLeft, Copy, Gift, Share2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Spinner } from "@xray/ui/components/spinner";
import { ReferralState, referral as referralApi } from "../api/client";
import { formatPoints, POINTS_ICON } from "../points";
import { copyToClipboard, hapticImpact, shareToTelegram } from "../tg/webapp";

export default function InvitePage() {
  const navigate = useNavigate();
  const [state, setState] = useState<ReferralState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    referralApi
      .getState()
      .then(setState)
      .catch((e) => setError(e?.detail || String(e)));
  }, []);

  const inviteText = state
    ? `Подключайся к VPN и получи ${formatPoints(state.credit_grant)} по моему коду!`
    : "";

  const handleCopy = async () => {
    if (!state) return;
    hapticImpact("light");
    const ok = await copyToClipboard(state.code);
    if (ok) toast.success("Промокод скопирован");
    else toast.error("Не удалось скопировать");
  };

  const handleShare = () => {
    if (!state?.deeplink) return;
    hapticImpact("medium");
    shareToTelegram(state.deeplink, inviteText);
  };

  return (
    <div className="page">
      <div className="page-header">
        <Button variant="ghost" size="icon" onClick={() => navigate("/settings")} aria-label="Назад">
          <ArrowLeft />
        </Button>
        <div className="text-xl font-bold text-foreground">Пригласить друзей</div>
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
                <Gift className="w-3.5 h-3.5" /> Ваш промокод
              </span>
              <div className="m-0 text-center text-2xl font-bold text-foreground tracking-widest">
                {state.code}
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-2.5 w-full">
            <Button variant="outline" size="lg" className="w-full" onClick={handleCopy}>
              <Copy />
              Скопировать код
            </Button>
            <Button size="lg" className="w-full" onClick={handleShare} disabled={!state.deeplink}>
              <Share2 />
              Поделиться
            </Button>
          </div>

          <Card>
            <CardContent className="p-4 flex justify-around gap-4">
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">Куплено по коду</div>
                <div className="text-xl font-bold text-foreground">{state.days_purchased} дн.</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">Начислено вам</div>
                <div className="text-xl font-bold text-foreground">
                  {state.points_rewarded} {POINTS_ICON}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <p className="mb-2 mt-0 text-foreground">
                <b>Как это работает</b>
              </p>
              <p className="text-muted-foreground mb-0">
                Друг получает <b>{formatPoints(state.credit_grant)}</b> при активации
                кода. За каждые 30 дней покупок по вашему коду вы получаете{" "}
                <b>{formatPoints(state.points_reward_per_30)}</b> — всего до{" "}
                <b>{formatPoints(state.reward_cap_points)}</b>.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
