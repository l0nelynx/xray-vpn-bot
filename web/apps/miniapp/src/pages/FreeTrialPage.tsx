import { CheckCircleFilled, LoadingOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Space, Spin, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { free } from "../api/client";
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
  const params = useParams<{ mode: Mode }>();
  const mode: Mode = params.mode === "telemt" ? "telemt" : "vpn";

  const title = mode === "telemt" ? "Telegram Прокси" : "Попробовать бесплатно";
  const description =
    mode === "telemt"
      ? "Подпишитесь на наш канал, чтобы получить бесплатный Telegram-прокси."
      : "Подпишитесь на наш канал, чтобы получить бесплатную подписку VPN.";

  const [bootstrapping, setBootstrapping] = useState(true);
  const [newsUrl, setNewsUrl] = useState<string>("");
  const [waiting, setWaiting] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [claimError, setClaimError] = useState<string | null>(null);
  const [claimed, setClaimed] = useState<ClaimedState | null>(null);
  const [checking, setChecking] = useState(false);

  const startedAtRef = useRef<number>(0);
  const cancelledRef = useRef<boolean>(false);
  const timerRef = useRef<number | undefined>();

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
      setClaimError("Сетевая ошибка, повторите попытку.");
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
      setClaimError("Подписка на канал не найдена. Подпишитесь и попробуйте снова.");
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
      <div className="page" style={{ textAlign: "center", paddingTop: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (claimed) {
    return (
      <div className="page">
        <Card style={{ textAlign: "center" }}>
          <CheckCircleFilled style={{ fontSize: 56, color: "#52c41a" }} />
          <Typography.Title level={3} style={{ marginTop: 16 }}>
            {mode === "telemt" ? "Прокси готов" : "Подписка активна"}
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            {claimed.alreadyActive
              ? "У вас уже есть активный доступ. Используйте кнопку ниже."
              : "Спасибо за подписку! Нажмите кнопку, чтобы подключиться."}
          </Typography.Paragraph>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Button type="primary" size="large" block onClick={openConnect}>
              Подключить
            </Button>
            <Button size="large" block onClick={() => navigate("/", { replace: true })}>
              На главную
            </Button>
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        {title}
      </Typography.Title>

      <Card>
        <Typography.Paragraph>{description}</Typography.Paragraph>

        {claimError && (
          <Alert
            type="error"
            showIcon
            title={claimError}
            style={{ marginBottom: 16 }}
            closable
            onClose={() => setClaimError(null)}
          />
        )}

        {timedOut && !waiting && (
          <Alert
            type="warning"
            showIcon
            title="Не удалось подтвердить подписку"
            description="Убедитесь, что вы подписались на канал, и нажмите «Проверить»."
            style={{ marginBottom: 16 }}
          />
        )}

        {waiting && (
          <Card type="inner" style={{ textAlign: "center", marginBottom: 16 }}>
            <LoadingOutlined style={{ fontSize: 36 }} spin />
            <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              Проверяем подписку…
            </Typography.Paragraph>
          </Card>
        )}

        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Button
            type="primary"
            size="large"
            block
            onClick={onSubscribeClick}
            disabled={!newsUrl || waiting}
          >
            Подписаться
          </Button>
          <Button size="large" block onClick={onManualCheck} loading={checking} disabled={waiting}>
            Проверить
          </Button>
          <Button size="large" block onClick={() => navigate("/", { replace: true })}>
            Назад
          </Button>
        </Space>
      </Card>
    </div>
  );
}

function humanizeDetail(detail: string): string {
  switch (detail) {
    case "create_failed":
      return "Не удалось создать подписку. Попробуйте позже.";
    case "update_failed":
      return "Не удалось обновить подписку. Попробуйте позже.";
    case "user is banned":
      return "Аккаунт заблокирован.";
    case "username required":
      return "Установите username в Telegram.";
    default:
      return detail;
  }
}
