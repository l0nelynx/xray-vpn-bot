import { Check, ChevronDown, CircleHelp, Copy, Download, Link2, ListPlus, Power, RotateCw, Star } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Spinner } from "@xray/ui/components/spinner";
import { Tabs, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import {
  api,
  type AppConfig,
  connect,
  type ConnectApp,
  type ConnectButton,
  type LocalizedText,
  type ManagedSubscription,
  type MeResponse,
  subscriptions as subscriptionsApi,
} from "../api/client";
import { AppIcon, LibIcon, resolveColor } from "../connect/icons";
import { useT } from "../i18n/LocaleContext";
import { copyToClipboard, hapticImpact, openLink, tg } from "../tg/webapp";
import { trackUx } from "../ux";

function tr(obj: LocalizedText | undefined, locale: string): string {
  if (!obj) return "";
  return obj[locale] ?? obj.en ?? Object.values(obj)[0] ?? "";
}

const PLATFORM_KEYS: Record<string, string> = {
  ios: "connect.platform.ios", android: "connect.platform.android", windows: "connect.platform.windows",
  macos: "connect.platform.macos", linux: "connect.platform.linux", appleTV: "connect.platform.appleTV",
  androidTV: "connect.platform.androidTV",
};
const PLATFORM_ORDER = ["ios", "android", "windows", "macos", "linux", "appleTV", "androidTV"];

function detectPlatform(available: string[]): string {
  const p = tg?.platform ?? "";
  if (p === "ios" && available.includes("ios")) return "ios";
  if (p === "android" && available.includes("android")) return "android";
  const ua = (navigator.userAgent || "").toLowerCase();
  if (/iphone|ipad|ipod/.test(ua) && available.includes("ios")) return "ios";
  if (/android/.test(ua) && available.includes("android")) return "android";
  if (/mac os x|macintosh/.test(ua) && available.includes("macos")) return "macos";
  if (/windows/.test(ua) && available.includes("windows")) return "windows";
  if (/linux/.test(ua) && available.includes("linux")) return "linux";
  return available[0] || "";
}

function fillLink(link: string, subUrl: string, username: string): string {
  const hashIdx = link.indexOf("#");
  const before = hashIdx >= 0 ? link.slice(0, hashIdx) : link;
  const after = hashIdx >= 0 ? link.slice(hashIdx) : "";
  const queryAware = before
    .replace(/([?&](?:url|name)=)\{\{SUBSCRIPTION_LINK\}\}/g, (_m, prefix: string) => prefix + encodeURIComponent(subUrl))
    .replace(/([?&](?:url|name)=)\{\{USERNAME\}\}/g, (_m, prefix: string) => prefix + encodeURIComponent(username))
    .split("{{SUBSCRIPTION_LINK}}").join(subUrl)
    .split("{{USERNAME}}").join(username);
  const hash = after
    .split("{{SUBSCRIPTION_LINK}}").join(encodeURIComponent(subUrl))
    .split("{{USERNAME}}").join(encodeURIComponent(username));
  return queryAware + hash;
}

type VerificationState = "idle" | "checking" | "connected" | "unknown" | "timeout";

export default function ConnectPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t, locale } = useT();
  const requestedId = Number(searchParams.get("subscription_id") || 0) || null;
  const source = searchParams.get("source") || "tab";
  const mockPlatform = import.meta.env.VITE_MOCK_API === "1" ? searchParams.get("mock_platform") : null;
  const previewTimeout = import.meta.env.VITE_MOCK_API === "1" && searchParams.get("preview_timeout") === "1";
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [subscriptions, setSubscriptions] = useState<ManagedSubscription[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(requestedId);
  const [subUrl, setSubUrl] = useState("");
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platform, setPlatform] = useState("");
  const [openApp, setOpenApp] = useState<string | null>(null);
  const [installOpened, setInstallOpened] = useState(false);
  const [addOpened, setAddOpened] = useState(false);
  const [verification, setVerification] = useState<VerificationState>("idle");
  const verificationDeadline = useRef(0);

  const applySelected = useCallback((items: ManagedSubscription[], meResp: MeResponse, id: number | null) => {
    const selected = id ? items.find((item) => item.id === id) : items.find((item) => item.is_primary);
    const fallback = meResp.subscription;
    if (id && !selected) throw new Error(t("subscriptions.notFound"));
    setSelectedId(selected?.id || fallback?.subscription_id || null);
    setSubUrl(selected?.subscription_url || fallback?.subscription_url || "");
    const connectionState = selected?.connection_state || fallback?.connection_state || "unknown";
    setVerification(connectionState === "connected" ? "connected" : connectionState === "unknown" ? "unknown" : "idle");
  }, [t]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [config, meResp, subscriptionsResp] = await Promise.all([
          connect.getAppConfig(), api.get<MeResponse>("/me"), subscriptionsApi.list().catch(() => ({ subscriptions: [] })),
        ]);
        if (!alive) return;
        setCfg(config); setSubscriptions(subscriptionsResp.subscriptions); setUsername(meResp.user?.username || "");
        applySelected(subscriptionsResp.subscriptions, meResp, requestedId);
        setPlatform(mockPlatform && config.platforms[mockPlatform] ? mockPlatform : detectPlatform(Object.keys(config.platforms)));
        trackUx({ name: "connect_started", subscription_id: requestedId || undefined, source });
      } catch (reason: any) {
        if (alive) setError(reason?.detail || reason?.message || String(reason));
      } finally { if (alive) setLoading(false); }
    })();
    return () => { alive = false; };
  }, [applySelected, mockPlatform, requestedId, source]);

  const platforms = useMemo(() => {
    if (!cfg) return [];
    const keys = Object.keys(cfg.platforms);
    return PLATFORM_ORDER.filter((item) => keys.includes(item)).concat(keys.filter((item) => !PLATFORM_ORDER.includes(item)));
  }, [cfg]);
  const apps: ConnectApp[] = useMemo(() => {
    if (!cfg || !platform) return [];
    return [...(cfg.platforms[platform]?.apps ?? [])].sort((a, b) => Number(!!b.featured) - Number(!!a.featured));
  }, [cfg, platform]);
  useEffect(() => { setOpenApp(apps[0]?.name || null); }, [apps]);

  const verifyOnce = useCallback(async (): Promise<VerificationState> => {
    try {
      const [meResp, subscriptionsResp] = await Promise.all([
        api.get<MeResponse>("/me"), subscriptionsApi.list().catch(() => ({ subscriptions: [] })),
      ]);
      const selected = selectedId ? subscriptionsResp.subscriptions.find((item) => item.id === selectedId) : null;
      const connectionState = selected?.connection_state || meResp.subscription?.connection_state || "unknown";
      if (connectionState === "connected") {
        setVerification("connected");
        trackUx({ name: "connection_verified", subscription_id: selectedId || undefined, platform, source });
        hapticImpact("medium");
        return "connected";
      }
      if (connectionState === "unknown") { setVerification("unknown"); return "unknown"; }
      setVerification("checking");
      return "checking";
    } catch { setVerification("unknown"); return "unknown"; }
  }, [platform, selectedId, source]);

  const startVerification = useCallback(() => {
    verificationDeadline.current = Date.now() + (previewTimeout ? 0 : 60_000);
    setVerification("checking");
    void verifyOnce();
  }, [previewTimeout, verifyOnce]);

  useEffect(() => {
    if (verification !== "checking") return;
    let timer: number | undefined;
    const tick = async () => {
      if (document.visibilityState !== "visible") return;
      const result = await verifyOnce();
      if (result !== "checking") return;
      if (Date.now() >= verificationDeadline.current) { setVerification("timeout"); return; }
      timer = window.setTimeout(tick, 3000);
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        verificationDeadline.current = Date.now() + 60_000;
        void tick();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    void tick();
    return () => { document.removeEventListener("visibilitychange", onVisibility); if (timer) window.clearTimeout(timer); };
  }, [verification, verifyOnce]);

  async function onButton(button: ConnectButton, appName: string) {
    hapticImpact("light");
    const url = fillLink(button.link, subUrl, username);
    if (button.type === "external") {
      setInstallOpened(true);
      trackUx({ name: "app_install_opened", subscription_id: selectedId || undefined, platform, app: appName, source });
    } else {
      setAddOpened(true);
      trackUx({ name: "subscription_add_opened", subscription_id: selectedId || undefined, platform, app: appName, source });
      startVerification();
    }
    if (button.type === "copyButton") {
      const ok = await copyToClipboard(url || subUrl);
      toast[ok ? "success" : "error"](ok ? t("connect.toast.copied") : t("connect.toast.copyFailed"));
      return;
    }
    if (!url) return;
    const needsRedirector = !/^https?:\/\//i.test(url) || url.includes("#") || /[?&]url=/.test(url);
    openLink(needsRedirector ? `${window.location.origin}/bot/miniapp/connect-open.html#${encodeURIComponent(url)}` : url);
  }

  async function copySub() {
    const ok = await copyToClipboard(subUrl);
    toast[ok ? "success" : "error"](ok ? t("connect.toast.linkCopied") : t("connect.toast.copyFailed"));
  }

  if (loading) return <div className="spinner-wrap"><Spinner className="h-8 w-8" /></div>;

  return (
    <div className="page connect-page">
      <header className="connect-header"><h1>{t("connect.title")}</h1><p>{t("connect.subtitle")}</p></header>
      {error && <Alert variant="destructive"><AlertTitle>{error}</AlertTitle></Alert>}
      {!subUrl ? (
        <Card><CardContent className="connect-empty"><div className="onboarding-glyph"><Link2 /></div><h2>{t("connect.emptyTitle")}</h2><p>{t("connect.emptyBody")}</p><Button size="lg" className="w-full" onClick={() => navigate("/buy")}>{t("home.buy")}</Button></CardContent></Card>
      ) : (
        <>
          {subscriptions.length > 1 && <div className="chip-row-wrap"><div className="chip-row">{subscriptions.map((item, index) => <button key={item.id} className={`plan-chip${selectedId === item.id ? " active" : ""}`} onClick={() => navigate(`/connect?subscription_id=${item.id}`, { replace: true })}>{item.label && item.label !== "Marketplace order" ? item.label : t("connect.subscriptionLabel", { number: index + 1 })}</button>)}</div></div>}

          <Card className="connect-progress-card">
            <CardContent className="p-4">
              <div className="connection-rail" aria-label={t("connect.stepsAria")}>
                <span className={installOpened || addOpened || verification === "connected" ? "done" : "active"}><Download /></span><i />
                <span className={addOpened || verification === "connected" ? "done" : installOpened ? "active" : ""}><ListPlus /></span><i />
                <span className={verification === "connected" ? "done" : addOpened ? "active" : ""}><Power /></span>
              </div>
              <div className="connection-labels"><span>{t("connect.step.install")}</span><span>{t("connect.step.add")}</span><span>{t("connect.step.enable")}</span></div>
            </CardContent>
          </Card>

          {platforms.length > 1 && <Tabs className="platform-tabs" value={platform} onValueChange={setPlatform}><TabsList>{platforms.map((item) => <TabsTrigger key={item} value={item}>{PLATFORM_KEYS[item] ? t(PLATFORM_KEYS[item]) : item}</TabsTrigger>)}</TabsList></Tabs>}

          <div className="connect-apps">{apps.map((app) => {
            const isOpen = openApp === app.name;
            return <Card key={app.name} className="connect-app">
              <button className="connect-app__header" onClick={() => setOpenApp(isOpen ? null : app.name)}>
                <AppIcon library={cfg?.svgLibrary} name={app.name} iconKey={app.svgIconKey} size={40} />
                <span><strong>{app.name}</strong><small>{app.featured ? t("connect.recommendedBody") : t("connect.alternativeBody")}</small></span>
                {app.featured && <Badge variant="warning"><Star />{t("connect.featured")}</Badge>}
                <ChevronDown className={isOpen ? "rotated" : ""} />
              </button>
              {isOpen && <div className="connect-app__body">{app.blocks.map((block, index) => {
                const color = resolveColor(block.svgIconColor);
                return <div className="guide-block" key={index}>
                  <span className="guide-block__icon"><LibIcon library={cfg?.svgLibrary} name={block.svgIconKey} color={color} size={16} /></span>
                  <div><strong>{tr(block.title, locale)}</strong>{block.description && <p>{tr(block.description, locale)}</p>}
                    <div className="guide-buttons">{block.buttons.map((button, buttonIndex) => <Button key={buttonIndex} variant={button.type === "subscriptionLink" ? "default" : "outline"} onClick={() => void onButton(button, app.name)}><LibIcon library={cfg?.svgLibrary} name={button.svgIconKey} size={15} />{tr(button.text, locale)}</Button>)}</div>
                  </div>
                </div>;
              })}</div>}
            </Card>;
          })}</div>

          <Alert variant={verification === "unknown" || verification === "timeout" ? "warning" : "default"} className={`connect-verification ${verification}`}>
            {verification === "connected" ? <Check /> : verification === "checking" ? <Spinner /> : verification === "unknown" || verification === "timeout" ? <CircleHelp /> : <RotateCw />}
            <AlertTitle>{verification === "connected" ? t("connect.verifiedTitle") : verification === "checking" ? t("connect.checkingTitle") : verification === "unknown" ? t("connect.unknownTitle") : verification === "timeout" ? t("connect.timeoutTitle") : t("connect.returnTitle")}</AlertTitle>
            <AlertDescription>{verification === "connected" ? t("connect.verifiedBody") : verification === "checking" ? t("connect.checkingBody") : verification === "unknown" ? t("connect.unknownBody") : verification === "timeout" ? t("connect.timeoutBody") : t("connect.returnBody")}</AlertDescription>
          </Alert>
          {verification !== "connected" && <Button variant="outline" className="w-full" onClick={startVerification}><RotateCw />{t("connect.checkAgain")}</Button>}
          {(verification === "timeout" || verification === "unknown") && <Button variant="ghost" className="w-full" onClick={() => { trackUx({ name: "connection_help_opened", subscription_id: selectedId || undefined, platform, source }); navigate("/support"); }}>{t("connect.openHelp")}</Button>}

          <Card className="manual-setup"><details><summary>{t("connect.manualTitle")}</summary><div className="px-4 pb-4"><p>{t("connect.subLinkLabel")}</p><code>{subUrl}</code><Button variant="outline" className="w-full" onClick={() => void copySub()}><Copy />{t("connect.copyLink")}</Button></div></details></Card>
        </>
      )}
    </div>
  );
}
