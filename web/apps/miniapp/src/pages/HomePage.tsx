import { ArrowRight, Link as LinkIcon, RefreshCw, Wifi } from "lucide-react";
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { MeResponse } from "../api/client";
import SubscriptionCard from "../components/SubscriptionCard";

interface Props {
  me: MeResponse;
  reload: () => void;
  refresh: () => void;
}

export default function HomePage({ me, reload, refresh }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const sub = me.subscription;
  const username = me.user?.username;

  const lastReloadKey = useRef<string>("");
  useEffect(() => {
    const key = location.key || "default";
    if (lastReloadKey.current !== key) {
      lastReloadKey.current = key;
      refresh();
    }
  }, [location.key, refresh]);

  return (
    <div className="page">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="text-[22px] font-bold text-foreground tracking-tight">
            {username ? `@${username}` : "Подписка"}
          </div>
          <div className="text-[13px] text-muted-foreground mt-0.5">
            VPN аккаунт
          </div>
        </div>
        <Button
          className="refresh-fab"
          size="icon"
          variant="outline"
          onClick={reload}
          aria-label="Обновить"
        >
          <RefreshCw />
        </Button>
      </div>

      {sub ? (
        <div className="flex flex-col gap-2.5 w-full">
          <SubscriptionCard sub={sub} />

          {sub.status === "active" && sub.subscription_url && (
            <Button size="lg" className="w-full" onClick={() => navigate("/connect")}>
              <LinkIcon />
              Подключиться
            </Button>
          )}

          <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/buy")}>
            <ArrowRight />
            {sub.status === "active" ? "Продлить подписку" : "Купить подписку"}
          </Button>

          <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/free/telemt")}>
            <Wifi />
            Telegram Прокси
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5 w-full">
          <Card>
            <CardContent className="p-7 px-5 text-center">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-3.5">
                <Wifi className="text-foreground w-6 h-6" />
              </div>
              <div className="text-[17px] font-semibold text-foreground mb-2">
                Нет активной подписки
              </div>
              <div className="text-sm text-muted-foreground leading-relaxed">
                Выберите тариф или активируйте пробный доступ
              </div>
            </CardContent>
          </Card>

          <Button size="lg" className="w-full" onClick={() => navigate("/buy")}>
            Купить подписку
          </Button>
          <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/free/vpn")}>
            Попробовать бесплатно
          </Button>
          <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/free/telemt")}>
            <Wifi />
            Telegram Прокси
          </Button>
        </div>
      )}
    </div>
  );
}
