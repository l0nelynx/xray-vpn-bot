import { CheckCircleFilled, LoadingOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Space, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, MeResponse } from "../api/client";
import { hapticImpact, openLink } from "../tg/webapp";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000;

interface LocationState {
  paymentUrl?: string;
  baselineExpireIso?: string | null;
  baselineDaysLeft?: number;
}

export default function BuySuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as LocationState;

  const [me, setMe] = useState<MeResponse | null>(null);
  const [done, setDone] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const startedAt = useRef<number>(Date.now());

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const fresh = await api.get<MeResponse>("/me");
        if (cancelled) return;
        setMe(fresh);
        const sub = fresh.subscription;
        const updated =
          sub != null &&
          (sub.expire_iso !== (state.baselineExpireIso ?? null) ||
            sub.days_left !== (state.baselineDaysLeft ?? 0));
        if (updated && sub?.subscription_url) {
          setDone(true);
          hapticImpact("medium");
          return;
        }
      } catch {
        /* keep polling */
      }
      if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
        setTimedOut(true);
        return;
      }
      timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [state.baselineDaysLeft, state.baselineExpireIso]);

  const subUrl = me?.subscription?.subscription_url;

  if (done && subUrl) {
    return (
      <div className="page">
        <Card style={{ textAlign: "center" }}>
          <CheckCircleFilled style={{ fontSize: 56, color: "#52c41a" }} />
          <Typography.Title level={3} style={{ marginTop: 16 }}>
            Оплата получена
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Подписка активирована. Откройте ссылку, чтобы подключиться:
          </Typography.Paragraph>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Button type="primary" size="large" block onClick={() => openLink(subUrl)}>
              Открыть подписку
            </Button>
            <Button size="large" block onClick={() => navigate("/", { replace: true })}>
              На главную
            </Button>
          </Space>
        </Card>
      </div>
    );
  }

  if (timedOut) {
    return (
      <div className="page">
        <Alert
          type="warning"
          title="Подтверждение оплаты заняло больше времени, чем ожидалось"
          description="Если деньги уже списаны — подписка появится в течение нескольких минут. Откройте главную и нажмите «Обновить»."
        />
        <div style={{ marginTop: 16 }}>
          <Button block size="large" onClick={() => navigate("/", { replace: true })}>
            На главную
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Card style={{ textAlign: "center" }}>
        <LoadingOutlined style={{ fontSize: 48 }} spin />
        <Typography.Title level={4} style={{ marginTop: 16 }}>
          Ждём подтверждение оплаты…
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          Это занимает обычно несколько секунд. Не закрывайте окно.
        </Typography.Paragraph>
        {state.paymentUrl && (
          <Button block onClick={() => openLink(state.paymentUrl!)}>
            Открыть страницу оплаты ещё раз
          </Button>
        )}
      </Card>
    </div>
  );
}
