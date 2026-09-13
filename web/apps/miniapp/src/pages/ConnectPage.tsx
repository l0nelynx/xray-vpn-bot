import { ArrowLeft, Check, ChevronRight, CircleHelp, Copy, Download, ExternalLink, Link2, Monitor, QrCode, RotateCw, Smartphone, Star, Tv } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@xray/ui/components/dialog";
import { Spinner } from "@xray/ui/components/spinner";
import { api, connect, subscriptions as subscriptionsApi, type AppConfig, type ConnectButton, type ManagedSubscription, type MeResponse, type UxEvent, type UxEventName } from "../api/client";
import { AppIcon } from "../connect/icons";
import { buttonPurpose, detectPlatform, fillLink, PLATFORM_ORDER, recommendedApp, resolveStage, subscriptionState, tr } from "../connect/catalog";
import LinkDialog, { type LinkResource } from "../connect/LinkDialog";
import { useT } from "../i18n/LocaleContext";
import { copyToClipboard, hapticImpact, openLink, tg } from "../tg/webapp";
import { trackUx } from "../ux";

type ConnectionData = { items: ManagedSubscription[]; me: MeResponse };
type VerificationState = "idle" | "checking" | "connected" | "unknown" | "timeout";

export default function ConnectPage() {
  const navigate = useNavigate();
  const { t } = useT();
  const [params] = useSearchParams();
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [data, setData] = useState<ConnectionData | null>(null);
  const [dataError, setDataError] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setDataError(false); setCatalogError(false);
    void connect.getAppConfig().then((config) => {
      if (!config?.platforms || typeof config.platforms !== "object") throw new Error("Invalid catalog");
      if (alive) setCfg(config);
    }).catch(() => { if (alive) setCatalogError(true); });
    void Promise.all([api.get<MeResponse>("/me"), subscriptionsApi.list().catch(() => null)])
      .then(([me, list]) => { if (alive) setData({ me, items: list?.subscriptions ?? [] }); })
      .catch(() => { if (alive) setDataError(true); });
    return () => { alive = false; };
  }, [attempt]);
  const requestedId = Number(params.get("subscription_id")) || null;
  const selected = data?.items.find((item) => requestedId ? item.id === requestedId : item.is_primary);
  const fallback = data?.me.subscription;
  const canFallback = !requestedId || requestedId === fallback?.subscription_id;
  const selectedId = selected?.id ?? (canFallback ? fallback?.subscription_id : null) ?? null;
  const subUrl = selected?.subscription_url ?? (canFallback ? fallback?.subscription_url : "") ?? "";
  const retry = () => setAttempt((value) => value + 1);
  if (dataError) return <div className="page connect-page"><h1>{t("connect.title")}</h1><Alert variant="warning"><AlertTitle>{t("connect.loadFailed")}</AlertTitle></Alert><Button onClick={retry}>{t("connect.retry")}</Button></div>;
  if (!data) return <div className="spinner-wrap"><Spinner className="h-8 w-8" /></div>;
  if (requestedId && !selectedId) return <div className="page connect-page"><h1>{t("connect.title")}</h1><Alert variant="warning"><AlertTitle>{t("subscriptions.notFound")}</AlertTitle></Alert><Button onClick={() => navigate("/subscriptions")}>{t("connect.chooseSubscription")}</Button></div>;
  if (!subUrl) return <div className="page connect-page"><h1>{t("connect.title")}</h1><Card><CardContent className="connect-empty"><div className="onboarding-glyph"><Link2 /></div><h2>{t("connect.emptyTitle")}</h2><p>{t("connect.emptyBody")}</p><Button size="lg" className="w-full" onClick={() => navigate("/buy")}>{t("home.buy")}</Button></CardContent></Card></div>;
  return <ConnectFlow key={`${selectedId}:${subUrl}`} cfg={cfg} data={data} subUrl={subUrl} selectedId={selectedId} catalogError={catalogError} retry={retry} />;
}

function ConnectFlow({ cfg, data, subUrl, selectedId, catalogError, retry }: {
  cfg: AppConfig | null; data: ConnectionData; subUrl: string; selectedId: number | null; catalogError: boolean; retry: () => void;
}) {
  const { t, locale } = useT();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const other = params.get("device") === "other";
  const source = params.get("source") || "tab";
  const available = Object.keys(cfg?.platforms ?? {}).filter((key) => Array.isArray(cfg?.platforms[key]?.apps));
  const platforms = PLATFORM_ORDER.filter((key) => available.includes(key)).concat(available.filter((key) => !PLATFORM_ORDER.includes(key)));
  const platform = platforms.includes(params.get("platform") || "") ? params.get("platform")! : "";
  const allApps = cfg?.platforms[platform]?.apps ?? [];
  const recommendation = recommendedApp(allApps);
  const apps = useMemo(() => [...allApps].sort((a, b) => Number(b.name === recommendation) - Number(a.name === recommendation)), [allApps, recommendation]);
  const app = apps.find((item) => item.name === params.get("app"));
  const stage = resolveStage(params.get("step"), platform, app);
  const mockPlatform = import.meta.env.VITE_MOCK_API === "1" ? params.get("mock_platform") : null;
  const detected = mockPlatform && platforms.includes(mockPlatform) ? mockPlatform : detectPlatform(platforms, tg?.platform ?? "", navigator.userAgent);
  const [resource, setResource] = useState<LinkResource | null>(null);
  const resourceTrigger = useRef<HTMLElement | null>(null);
  const [choosingSubscription, setChoosingSubscription] = useState(false);
  const [verification, setVerification] = useState<VerificationState>("idle");
  const [verificationRun, setVerificationRun] = useState(0);
  const verificationContext = useRef("");
  const heading = useRef<HTMLHeadingElement>(null);
  const subscriptionLabel = (item: ManagedSubscription, index: number) => item.label && item.label !== "Marketplace order" ? item.label : t("connect.subscriptionLabel", { number: index + 1 });
  const selectedIndex = data.items.findIndex((item) => item.id === selectedId);
  const platformLabel = (key: string) => PLATFORM_ORDER.includes(key) ? t(`connect.platform.${key}`) : key;
  const subscriptionResource: LinkResource = { url: subUrl, title: t("connect.subLinkLabel"), kind: "subscription", qr: false };
  const track = useCallback((name: UxEventName, extra: Partial<UxEvent> = {}) => trackUx({
    name, subscription_id: selectedId ?? undefined, platform: platform || undefined,
    app: app?.name, source, device_mode: other ? "other" : "current", ...extra,
  }), [app?.name, other, platform, selectedId, source]);
  const startTracked = useRef(false);
  useEffect(() => {
    if (!startTracked.current) { track("connect_started"); startTracked.current = true; }
  }, [track]);
  const guideTracked = useRef("");
  useEffect(() => {
    const key = stage === "guide" ? `${platform}:${app?.name}:${other}` : "";
    if (key && key !== guideTracked.current) track("connect_guide_opened");
    guideTracked.current = key;
  }, [stage, platform, app?.name, other, track]);

  const move = useCallback((changes: Record<string, string | null>, replace = false) => {
    const next = new URLSearchParams(params);
    if (selectedId) next.set("subscription_id", String(selectedId));
    for (const [key, value] of Object.entries(changes)) { if (value === null) next.delete(key); else next.set(key, value); }
    setResource(null); setChoosingSubscription(false);
    setParams(next, { replace });
  }, [params, selectedId, setParams]);
  const back = useCallback(() => {
    if (resource) { setResource(null); return; }
    if (choosingSubscription) { setChoosingSubscription(false); return; }
    if (stage === "guide") move({ step: "clients" });
    else if (stage === "clients") move({ step: "platform" });
    else navigate("/");
  }, [choosingSubscription, move, navigate, resource, stage]);
  useEffect(() => {
    const button = tg?.BackButton;
    if (!button) return;
    button.show(); button.onClick(back);
    return () => { button.offClick(back); button.hide(); };
  }, [back]);
  useEffect(() => {
    setResource(null); setVerification("idle"); setVerificationRun(0);
    verificationContext.current = "";
  }, [stage, platform, app?.name, other]);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    document.getElementById("root")?.scrollTo({ top: 0, behavior: "instant" });
    heading.current?.focus({ preventScroll: true });
  }, [stage, platform, app?.name]);

  const previewTimeout = import.meta.env.VITE_MOCK_API === "1" && params.get("preview_timeout") === "1";
  useEffect(() => {
    if (!verificationRun || stage !== "guide" || other || verificationContext.current !== `${platform}:${app?.name}`) return;
    let alive = true;
    let busy = false;
    let timer: number | undefined;
    const deadline = Date.now() + (previewTimeout ? 0 : 60_000);
    const tick = async () => {
      if (!alive || busy || document.visibilityState !== "visible") return;
      busy = true;
      try {
        const [me, list] = await Promise.all([api.get<MeResponse>("/me"), subscriptionsApi.list().catch(() => null)]);
        if (!alive) return;
        const state = subscriptionState(selectedId, list?.subscriptions ?? [], me.subscription);
        if (state === "connected") { setVerification("connected"); track("connection_verified", { outcome: "subscription_history" }); alive = false; return; }
        if (state === "unknown") { setVerification("unknown"); alive = false; return; }
        if (Date.now() >= deadline) { setVerification("timeout"); alive = false; return; }
        timer = window.setTimeout(tick, 3000);
      } catch { if (alive) { setVerification("unknown"); alive = false; } }
      finally { busy = false; }
    };
    const onVisibility = () => { if (timer) window.clearTimeout(timer); void tick(); };
    setVerification("checking");
    document.addEventListener("visibilitychange", onVisibility);
    void tick();
    return () => { alive = false; if (timer) window.clearTimeout(timer); document.removeEventListener("visibilitychange", onVisibility); };
  }, [verificationRun, stage, other, platform, app?.name, selectedId, previewTimeout, track]);

  function startVerification() {
    verificationContext.current = `${platform}:${app?.name}`;
    setVerificationRun((value) => value + 1);
  }

  function showResource(value: LinkResource) {
    resourceTrigger.current = document.activeElement as HTMLElement;
    setResource(value);
    if (value.qr) track("connect_qr_opened", { resource: value.kind });
  }
  async function copyResource(value: LinkResource) {
    const trigger = document.activeElement as HTMLElement;
    const ok = await copyToClipboard(value.url);
    toast[ok ? "success" : "error"](t(ok ? "connect.toast.linkCopied" : "connect.toast.copyFailed"));
    if (ok) { track("connect_link_copied", { resource: value.kind }); hapticImpact("light"); }
    else if (!resource) { resourceTrigger.current = trigger; setResource({ ...value, qr: false }); }
  }
  async function onButton(button: ConnectButton) {
    const url = fillLink(button.link, subUrl, data.me.user?.username ?? "") || (button.type === "copyButton" ? subUrl : "");
    if (!url) { toast.error(t("connect.linkUnavailable")); return; }
    const purpose = buttonPurpose(button);
    if (button.type === "copyButton") { await copyResource({ url, title: tr(button.text, locale), kind: url === subUrl ? "subscription" : purpose, qr: false }); return; }
    hapticImpact("light");
    const needsRedirector = !/^https?:\/\//i.test(url) || url.includes("#") || /[?&]url=/.test(url);
    try {
      openLink(needsRedirector ? `${window.location.origin}/bot/miniapp/connect-open.html#${encodeURIComponent(url)}` : url);
      if (purpose === "install") track("app_install_opened");
      else if (purpose === "account" || purpose === "import") {
        track("subscription_add_opened");
        if (!other) startVerification();
      }
    } catch { toast.error(t("connect.linkUnavailable")); }
  }
  function renderButton(button: ConnectButton, index: number) {
    const url = fillLink(button.link, subUrl, data.me.user?.username ?? "");
    const purpose = buttonPurpose(button);
    const label = tr(button.text, locale);
    const shared: LinkResource = { url, title: `${app?.name} · ${platformLabel(platform)} — ${label}`, kind: purpose, qr: false };
    if (other && /^https?:\/\//i.test(url) && button.type === "external") return <div className="connect-transfer-resource" key={index}>
      <span>{label}</span><div className="connect-resource-actions">
        <Button variant="outline" onClick={() => void copyResource(shared)}><Copy />{t(purpose === "install" ? "connect.copyApp" : "connect.copyLink")}</Button>
        <Button variant="outline" className="connect-qr-button" aria-label={t("connect.qrFor", { title: label })} onClick={() => showResource({ ...shared, qr: true })}><QrCode />QR</Button>
      </div>
    </div>;
    if (other && button.type === "subscriptionLink") return <p className="connect-caption" key={index}>{t("connect.useSubscriptionAbove")}</p>;
    return <Button key={index} variant={button.secondary ? "ghost" : purpose === "import" || purpose === "account" ? "default" : "outline"} onClick={() => void onButton(button)}>
      {button.type === "copyButton" ? <Copy /> : purpose === "install" ? <Download /> : <ExternalLink />}{label}
    </Button>;
  }

  const title = stage === "platform" ? t("connect.title") : stage === "clients" ? t("connect.chooseApp") : t("connect.guideTitle", { app: app!.name, platform: platformLabel(platform) });
  return <div className="page connect-page">
    <header className="connect-heading">
      {stage !== "platform" && <Button size="icon" variant="ghost" aria-label={t("connect.backAria")} onClick={back}><ArrowLeft /></Button>}
      <h1 ref={heading} tabIndex={-1}>{title}</h1>
    </header>
    <section className="connect-subscription" aria-label={t("connect.subLinkLabel")}>
      <div className="connect-subscription-label"><span>{t("connect.subLinkLabel")}</span>
        {data.items.length > 1 && <Dialog open={choosingSubscription} onOpenChange={setChoosingSubscription}>
          <DialogTrigger asChild><button className="connect-text-button connect-subscription-picker">{selectedIndex >= 0 ? subscriptionLabel(data.items[selectedIndex], selectedIndex) : t("connect.change")}<ChevronRight /></button></DialogTrigger>
          <DialogContent className="connect-link-dialog" overlayClassName="connect-modal-overlay" closeLabel={t("connect.closeDialog")}><DialogTitle>{t("connect.chooseSubscription")}</DialogTitle><DialogDescription>{t("connect.chooseSubscriptionHint")}</DialogDescription><div className="connect-choice-list">{data.items.map((item, index) => <button className="connect-choice" key={item.id} onClick={() => move({ subscription_id: String(item.id) }, true)}><span>{subscriptionLabel(item, index)}</span>{item.id === selectedId ? <Check /> : <ChevronRight />}</button>)}</div><DialogClose asChild><Button variant="ghost">{t("connect.close")}</Button></DialogClose></DialogContent>
        </Dialog>}
      </div>
      <input className="connect-subscription-url" aria-label={t("connect.subLinkLabel")} readOnly value={subUrl} onFocus={(event) => event.target.select()} />
      <div className="connect-resource-actions">
        <Button variant="outline" onClick={() => void copyResource(subscriptionResource)}><Copy />{t("connect.copyLink")}</Button>
        {other && <Button variant="outline" className="connect-qr-button" aria-label={t("connect.qrFor", { title: t("connect.subLinkLabel") })} onClick={() => showResource({ ...subscriptionResource, qr: true })}><QrCode />QR</Button>}
      </div>
    </section>
    <label className="connect-device-switch">
      <span className="connect-device-checkbox">
        <input type="checkbox" checked={other} onChange={(event) => move({ device: event.target.checked ? "other" : null })} />
        <Check aria-hidden="true" />
      </span>
      <span>{t("connect.otherDevice")}</span>
    </label>
    {catalogError ? <Alert variant="warning"><AlertTitle>{t("connect.catalogFailed")}</AlertTitle><AlertDescription><p>{t("connect.catalogFailedHint")}</p><Button variant="outline" onClick={retry}>{t("connect.retry")}</Button></AlertDescription></Alert> : !cfg ? <div className="connect-loading"><Spinner /></div> : <>
      {stage === "platform" ? <>
        <h2 className="connect-question">{t(other ? "connect.chooseOtherPlatform" : "connect.choosePlatform")}</h2>
        <div className="connect-platform-grid">{platforms.map((key) => {
          const Icon = key === "ios" || key === "android" ? Smartphone : key.toLowerCase().includes("tv") ? Tv : Monitor;
          return <button className={`connect-platform-choice${platform === key ? " selected" : ""}`} key={key} onClick={() => {
            track("connect_platform_selected", { platform: key, app: undefined });
            move({ platform: key, app: key === platform ? params.get("app") : null, step: "clients" });
          }}><Icon /><span>{platformLabel(key)}{!other && detected === key && <small>{t("connect.detectedDevice")}</small>}</span><ChevronRight /></button>;
        })}</div>
        {!platforms.length && <p>{t("connect.noPlatforms")}</p>}
      </> : <>
        <div className="connect-context"><span>{platformLabel(platform)}{other && ` · ${t("connect.otherDeviceShort")}`}</span><button className="connect-text-button" onClick={() => move({ step: "platform" })}>{t("connect.changePlatform")}</button></div>
        {stage === "clients" ? <>
          <div className="connect-choice-list">{apps.map((item) => <button className={`connect-choice${item.name === app?.name ? " selected" : ""}`} key={item.name} onClick={() => {
            track("connect_app_selected", { app: item.name }); move({ app: item.name, step: "guide" });
          }}><AppIcon library={cfg.svgLibrary} name={item.name} iconKey={item.svgIconKey} size={32} /><span><strong>{item.name}</strong>{item.name === recommendation && <small className="connect-recommendation"><Star />{t("connect.featured")}</small>}</span><ChevronRight /></button>)}</div>
          {!apps.length && <p>{t("connect.noApps")}</p>}
        </> : <>
          <button className="connect-text-button connect-change-client" onClick={() => move({ step: "clients" })}>{t("connect.changeApp")}</button>
          {other && <p className="connect-transfer-hint">{t("connect.transferHint")}</p>}
          <ol className="connect-guide">{app!.blocks.map((block, index) => <li key={index}>
            <span className="connect-guide-number" aria-hidden="true">{index + 1}</span>
            <div className="connect-guide-content"><h2>{tr(block.title, locale)}</h2>
              {block.description && <p>{tr(other ? block.otherDescription ?? block.description : block.description, locale)}</p>}
              {block.buttons.length > 0 && <div className="connect-guide-buttons">{block.buttons.map(renderButton)}</div>}
            </div>
          </li>)}</ol>
          {!other && <section className="connect-verification-section">
            {verification !== "idle" && <Alert aria-live="polite" variant={verification === "unknown" || verification === "timeout" ? "warning" : "default"} className={`connect-verification ${verification}`}>
              {verification === "connected" ? <Check /> : verification === "checking" ? <Spinner /> : <CircleHelp />}
              <AlertTitle>{t(`connect.${verification === "connected" ? "verified" : verification}Title`)}</AlertTitle>
              <AlertDescription>{t(`connect.${verification === "connected" ? "verified" : verification}Body`)}</AlertDescription>
            </Alert>}
            <Button variant="outline" className="w-full" disabled={verification === "checking"} onClick={startVerification}><RotateCw />{t("connect.checkAgain")}</Button>
          </section>}
          <Button variant="ghost" className="w-full" onClick={() => { track("connection_help_opened"); navigate("/support"); }}><CircleHelp />{t("connect.openHelp")}</Button>
        </>}
      </>}
    </>}
    <LinkDialog resource={resource} onClose={() => setResource(null)} onCopy={copyResource} returnFocus={resourceTrigger} />
  </div>;
}
