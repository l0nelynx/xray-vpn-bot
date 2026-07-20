import { App as AntApp, Button, Collapse, Segmented, Spin, Tag, Typography } from "antd";
import { ArrowLeftOutlined, CopyOutlined, StarFilled } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  AppConfig,
  connect,
  ConnectApp,
  ConnectButton,
  LocalizedText,
  MeResponse,
} from "../api/client";
import { copyToClipboard, hapticImpact, openLink, tg } from "../tg/webapp";
import { AppIcon, LibIcon, resolveColor } from "../connect/icons";

const { Text } = Typography;

// MiniApp UI is Russian-first; fall back to English then any available locale.
const LANG = "ru";
function tr(obj?: LocalizedText): string {
  if (!obj) return "";
  return obj[LANG] ?? obj.en ?? Object.values(obj)[0] ?? "";
}

const PLATFORM_LABELS: Record<string, string> = {
  ios: "iOS",
  android: "Android",
  windows: "Windows",
  macos: "macOS",
  linux: "Linux",
  appleTV: "Apple TV",
  androidTV: "Android TV",
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
  return available[0];
}

function fillLink(link: string, subUrl: string, username: string): string {
  // Encode subscription/username when they land in a query (?url= / &url=)
  // or a #fragment so ?&= inside the value don't break URL parsing.
  const hashIdx = link.indexOf("#");
  const before = hashIdx >= 0 ? link.slice(0, hashIdx) : link;
  const after = hashIdx >= 0 ? link.slice(hashIdx) : "";

  const fillQueryAware = (s: string, value: string, user: string) => {
    // Prefer encoding for url= / name= style placeholders in query strings.
    let out = s.replace(
      /([?&](?:url|name)=)\{\{SUBSCRIPTION_LINK\}\}/g,
      (_m, prefix: string) => prefix + encodeURIComponent(value),
    );
    out = out.replace(
      /([?&](?:url|name)=)\{\{USERNAME\}\}/g,
      (_m, prefix: string) => prefix + encodeURIComponent(user),
    );
    // Remaining placeholders (path segments, custom schemes) stay raw.
    return out
      .split("{{SUBSCRIPTION_LINK}}").join(value)
      .split("{{USERNAME}}").join(user);
  };

  const fillHash = (s: string, value: string, user: string) =>
    s
      .split("{{SUBSCRIPTION_LINK}}").join(encodeURIComponent(value))
      .split("{{USERNAME}}").join(encodeURIComponent(user));

  return fillQueryAware(before, subUrl, username) + fillHash(after, subUrl, username);
}

export default function ConnectPage() {
  const navigate = useNavigate();
  const { message } = AntApp.useApp();

  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [subUrl, setSubUrl] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string>("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [config, meResp] = await Promise.all([
          connect.getAppConfig(),
          api.get<MeResponse>("/me"),
        ]);
        if (!alive) return;
        setCfg(config);
        setSubUrl(meResp.subscription?.subscription_url || "");
        setUsername(meResp.user?.username || "");
        const available = Object.keys(config.platforms);
        setPlatform(detectPlatform(available));
      } catch (e: any) {
        if (alive) setError(e?.detail || String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const platforms = useMemo(() => {
    if (!cfg) return [];
    const keys = Object.keys(cfg.platforms);
    return PLATFORM_ORDER.filter((p) => keys.includes(p)).concat(
      keys.filter((k) => !PLATFORM_ORDER.includes(k))
    );
  }, [cfg]);

  const apps: ConnectApp[] = useMemo(() => {
    if (!cfg || !platform) return [];
    const list = cfg.platforms[platform]?.apps ?? [];
    // Featured first, preserve original order otherwise.
    return [...list].sort((a, b) => Number(!!b.featured) - Number(!!a.featured));
  }, [cfg, platform]);

  async function onButton(btn: ConnectButton) {
    hapticImpact("light");
    const url = fillLink(btn.link, subUrl, username);
    if (btn.type === "copyButton") {
      const ok = await copyToClipboard(url);
      message[ok ? "success" : "error"](ok ? "Скопировано" : "Не удалось скопировать");
      return;
    }
    // Plain https without query/fragment (App Store / GitHub) — open directly.
    // Custom schemes and claim links (?url= / #url=) bounce through
    // connect-open.html so Telegram cannot strip the subscription payload.
    const needsRedirector =
      !/^https?:\/\//i.test(url) || url.includes("#") || /[?&]url=/.test(url);
    if (needsRedirector) {
      const redirector =
        `${window.location.origin}/bot/miniapp/connect-open.html#${encodeURIComponent(url)}`;
      openLink(redirector);
    } else {
      openLink(url);
    }
  }

  async function copySub() {
    if (!subUrl) return;
    hapticImpact("light");
    const ok = await copyToClipboard(subUrl);
    message[ok ? "success" : "error"](ok ? "Ссылка скопирована" : "Не удалось скопировать");
  }

  if (loading) {
    return (
      <div className="spinner-wrap">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
        <Button
          shape="circle"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
          aria-label="Назад"
        />
        <div style={{ fontSize: 20, fontWeight: 700, color: "#FFFFFF" }}>Подключение</div>
      </div>

      {error && (
        <Text style={{ color: "#FF7C7C", display: "block", marginBottom: 16 }}>{error}</Text>
      )}

      {/* Subscription link */}
      {subUrl && (
        <div
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.10)",
            borderRadius: 16,
            padding: 16,
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginBottom: 8 }}>
            Ссылка-подписка
          </div>
          <div
            style={{
              fontSize: 12,
              color: "rgba(255,255,255,0.65)",
              wordBreak: "break-all",
              fontFamily: "monospace",
              marginBottom: 12,
              lineHeight: 1.4,
            }}
          >
            {subUrl}
          </div>
          <Button block icon={<CopyOutlined />} onClick={copySub}>
            Скопировать ссылку
          </Button>
        </div>
      )}

      {/* Platform selector */}
      {platforms.length > 1 && (
        <div style={{ marginBottom: 16, overflowX: "auto" }}>
          <Segmented
            value={platform}
            onChange={(v) => setPlatform(String(v))}
            options={platforms.map((p) => ({ label: PLATFORM_LABELS[p] ?? p, value: p }))}
          />
        </div>
      )}

      {/* App guides */}
      <Collapse
        accordion
        bordered={false}
        defaultActiveKey={apps.length ? [apps[0].name] : []}
        style={{ background: "transparent" }}
        items={apps.map((app) => ({
          key: app.name,
          label: (
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <AppIcon
                library={cfg?.svgLibrary}
                name={app.name}
                iconKey={app.svgIconKey}
                size={36}
              />
              <span style={{ fontSize: 16, fontWeight: 600, color: "#FFFFFF" }}>{app.name}</span>
              {app.featured && (
                <Tag
                  color="gold"
                  icon={<StarFilled />}
                  style={{ marginInlineStart: "auto", marginInlineEnd: 0 }}
                >
                  Рекомендуем
                </Tag>
              )}
            </div>
          ),
          style: {
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.09)",
            borderRadius: 16,
            marginBottom: 10,
          },
          children: (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {app.blocks.map((block, bi) => {
                const color = resolveColor(block.svgIconColor);
                return (
                  <div key={bi}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span
                        style={{
                          width: 26,
                          height: 26,
                          borderRadius: 8,
                          background: `${color}22`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <LibIcon
                          library={cfg?.svgLibrary}
                          name={block.svgIconKey}
                          color={color}
                          size={15}
                        />
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: "#FFFFFF" }}>
                        {tr(block.title)}
                      </span>
                    </div>
                    {block.description && (
                      <div
                        style={{
                          fontSize: 13,
                          color: "rgba(255,255,255,0.55)",
                          lineHeight: 1.5,
                          marginBottom: block.buttons.length ? 10 : 0,
                          paddingInlineStart: 34,
                        }}
                      >
                        {tr(block.description)}
                      </div>
                    )}
                    {block.buttons.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 8,
                          paddingInlineStart: 34,
                        }}
                      >
                        {block.buttons.map((btn, qi) => (
                          <Button
                            key={qi}
                            type={btn.type === "subscriptionLink" ? "primary" : "default"}
                            icon={
                              <LibIcon
                                library={cfg?.svgLibrary}
                                name={btn.svgIconKey}
                                size={15}
                              />
                            }
                            onClick={() => onButton(btn)}
                          >
                            {tr(btn.text)}
                          </Button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ),
        }))}
      />
    </div>
  );
}
