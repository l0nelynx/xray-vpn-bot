import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Alert, AlertTitle, AlertDescription } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Spinner } from "@xray/ui/components/spinner";
import { free } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { hapticImpact, openLink, openTelegramLink } from "../tg/webapp";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 15 * 1000;

type Mode = "vpn" | "telemt";

interface ClaimedState {
  url: string;
  alreadyActive: boolean;
}

function openProxyLink(url: string) {
  // Telegram's openTelegramLink only accepts https://t.me/...
  // Convert tg://proxy?... and tg://socks?... to https://t.me/...
  const tgPrefix = "tg://";
  if (url.startsWith(tgPrefix)) {
    const httpsLink = "https://t.me/" + url.slice(tgPrefix.length);
    openTelegramLink(httpsLink);
    return;
  }
  if (url.startsWith("https://t.me/") || url.startsWith("http://t.me/")) {
    openTelegramLink(url);
    return;
  }
  openLink(url);
}

export default function FreeTrialPage() {
  const navigate = useNavigate();
  const { t } = useT();
  const params = useParams<{ mode: Mode }>();
  const mode: Mode = params.mode === "telemt" ? "telemt" : "vpn";

  const title = mode === "telemt" ? t("freeTrial.title.telemt") : t("freeTrial.title.vpn");
  const description =
    mode === "telemt" ? t("freeTrial.desc.telemt") : t("freeTrial.desc.vpn");

  const [bootstrapping, setBootstrapping] = useState(true);
  const [newsUrl, setNewsUrl] = useState<string>("");
  const [waiting, setWaiting] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [claimError, setClaimError] = useState<string | null>(null);
  const [claimed, setClaimed] = useState<ClaimedState | null>(null);
  const [checking, setChecking] = useState(false);

  const startedAtRef = useRef<number>(0);
  const cancelledRef = useRef<boolean>(false);
  const timerRef = useRef<number | undefined>(undefined);

  const humanizeDetail = (detail: string): string => {
    switch (detail) {
      case "create_failed":
        return t("freeTrial.error.createFailed");
      case "update_failed":
        return t("freeTrial.error.updateFailed");
      case "user is banned":
        return t("freeTrial.error.banned");
      default:
        return detail;
    }
  };

  const stopPolling = () => {
    cancelledRef.current = true;
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = undefined;
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status =
          mode === "vpn" ? await free.vpnStatus() : await free.telemtStatus();
        if (cancelled) return;
        setNewsUrl(status.news_url);
        if (status.has_access && status.url) {
          setClaimed({ url: status.url, alreadyActive: true });
        }
      } catch {
        /* fall through to subscribe flow */
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    })();
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [mode]);

  const tryClaim = async (): Promise<boolean> => {
    setClaimError(null);
    try {
      if (mode === "vpn") {
        const res = await free.claimVpn();
        if (res.ok && res.subscription_url) {
          setClaimed({ url: res.subscription_url, alreadyActive: res.detail === "already_active" });
          hapticImpact("medium");
          return true;
        }
        if (res.detail && res.detail !== "not subscribed") {
          setClaimError(humanizeDetail(res.detail));
        }
        return false;
      } else {
        const res = await free.claimTelemt();
        if (res.ok && res.link) {
          setClaimed({ url: res.link, alreadyActive: res.detail === "already_active" });
          hapticImpact("medium");
          return true;
        }
        if (res.detail && res.detail !== "not subscribed") {
          setClaimError(humanizeDetail(res.detail));
        }
        return false;
      }
    } catch {
      setClaimError(t("freeTrial.error.network"));
      return false;
    }
  };

  const startWaiting = () => {
    cancelledRef.current = false;
    setTimedOut(false);
    setWaiting(true);
    startedAtRef.current = Date.now();

    const tick = async () => {
      if (cancelledRef.current) return;
      const ok = await tryClaim();
      if (cancelledRef.current) return;
      if (ok) {
        setWaiting(false);
        return;
      }
      if (Date.now() - startedAtRef.current >= POLL_TIMEOUT_MS) {
        setTimedOut(true);
        setWaiting(false);
        return;
      }
      timerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS);
    };

    timerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS);
  };

  const onSubscribeClick = () => {
    if (newsUrl) {
      if (newsUrl.includes("t.me")) {
        openTelegramLink(newsUrl);
      } else {
        openLink(newsUrl);
      }
    }
    startWaiting();
  };

  const onManualCheck = async () => {
    if (checking) return;
    setChecking(true);
    stopPolling();
    setWaiting(false);
    const ok = await tryClaim();
    setChecking(false);
    if (!ok && !claimError) {
      setClaimError(t("freeTrial.error.notSubscribed"));
    }
  };

  const openConnect = () => {
    if (!claimed?.url) return;
    if (mode === "telemt") {
      openProxyLink(claimed.url);
    } else {
      openLink(claimed.url);
    }
  };

  if (bootstrapping) {
    return (
      <div className="page text-center pt-16">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (claimed) {
    return (
      <div className="page">
        <Card className="text-center">
          <CardContent className="p-6">
            <CheckCircle2 className="w-14 h-14 text-emerald-500 mx-auto" />
            <div className="text-xl font-bold text-foreground mt-4">
              {mode === "telemt" ? t("freeTrial.success.proxyReady") : t("freeTrial.success.subActive")}
            </div>
            <p className="text-muted-foreground mt-2 mb-5">
              {claimed.alreadyActive
                ? t("freeTrial.success.alreadyActive")
                : t("freeTrial.success.thanks")}
            </p>
            <div className="flex flex-col gap-3 w-full">
              <Button size="lg" className="w-full" onClick={openConnect}>
                {t("freeTrial.connect")}
              </Button>
              <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/", { replace: true })}>
                {t("freeTrial.toHome")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="text-xl font-bold text-foreground mb-4">{title}</div>

      <Card>
        <CardContent className="p-5 flex flex-col gap-4">
          <p className="m-0 text-foreground">{description}</p>

          {claimError && (
            <Alert variant="destructive">
              <AlertTitle>{claimError}</AlertTitle>
            </Alert>
          )}

          {timedOut && !waiting && (
            <Alert variant="warning">
              <AlertTitle>{t("freeTrial.timeoutTitle")}</AlertTitle>
              <AlertDescription>
                {t("freeTrial.timeoutBody")}
              </AlertDescription>
            </Alert>
          )}

          {waiting && (
            <Card className="text-center bg-muted">
              <CardContent className="p-5">
                <Loader2 className="animate-spin w-9 h-9 mx-auto" />
                <p className="text-muted-foreground mt-3 mb-0">
                  {t("freeTrial.checking")}
                </p>
              </CardContent>
            </Card>
          )}

          <div className="flex flex-col gap-3 w-full">
            <Button
              size="lg"
              className="w-full"
              onClick={onSubscribeClick}
              disabled={!newsUrl || waiting}
            >
              {t("freeTrial.subscribe")}
            </Button>
            <Button size="lg" variant="outline" className="w-full" onClick={onManualCheck} disabled={waiting || checking}>
              {checking ? <Spinner /> : null}
              {t("freeTrial.check")}
            </Button>
            <Button size="lg" variant="outline" className="w-full" onClick={() => navigate("/", { replace: true })}>
              {t("freeTrial.back")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
