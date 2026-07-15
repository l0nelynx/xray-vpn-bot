import {
  ArrowLeftOutlined,
  CopyOutlined,
  GiftOutlined,
  ShareAltOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Space,
  Spin,
  Statistic,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ReferralState, referral as referralApi } from "../api/client";
import { formatPoints, POINTS_ICON } from "../points";
import { copyToClipboard, hapticImpact, shareToTelegram } from "../tg/webapp";

export default function InvitePage() {
  const navigate = useNavigate();
  const [state, setState] = useState<ReferralState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

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
    if (ok) messageApi.success("Промокод скопирован");
    else messageApi.error("Не удалось скопировать");
  };

  const handleShare = () => {
    if (!state?.deeplink) return;
    hapticImpact("medium");
    shareToTelegram(state.deeplink, inviteText);
  };

  return (
    <div className="page">
      {contextHolder}
      <div className="page-header">
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/settings")}
          aria-label="Назад"
        />
        <Typography.Title level={3} style={{ margin: 0 }}>
          Пригласить друзей
        </Typography.Title>
      </div>

      {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} />}

      {!state && !error && (
        <div className="spinner-wrap">
          <Spin />
        </div>
      )}

      {state && (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card size="small" className="glass-success">
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              <Typography.Text type="secondary">
                <GiftOutlined /> Ваш промокод
              </Typography.Text>
              <Typography.Title
                level={2}
                copyable={false}
                style={{ margin: 0, letterSpacing: 2, textAlign: "center" }}
              >
                {state.code}
              </Typography.Title>
            </Space>
          </Card>

          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Button
              block
              size="large"
              icon={<CopyOutlined />}
              onClick={handleCopy}
            >
              Скопировать код
            </Button>
            <Button
              block
              size="large"
              type="primary"
              icon={<ShareAltOutlined />}
              onClick={handleShare}
              disabled={!state.deeplink}
            >
              Поделиться
            </Button>
          </Space>

          <Card size="small">
            <Space
              size="large"
              style={{ width: "100%", justifyContent: "space-around" }}
            >
              <Statistic
                title="Куплено по коду"
                value={state.days_purchased}
                suffix="дн."
              />
              <Statistic
                title="Начислено вам"
                value={state.points_rewarded}
                suffix={POINTS_ICON}
              />
            </Space>
          </Card>

          <Card size="small">
            <Typography.Paragraph style={{ marginBottom: 8 }}>
              <b>Как это работает</b>
            </Typography.Paragraph>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              Друг получает <b>{formatPoints(state.credit_grant)}</b> при активации
              кода. За каждые 30 дней покупок по вашему коду вы получаете{" "}
              <b>{formatPoints(state.points_reward_per_30)}</b> — всего до{" "}
              <b>{formatPoints(state.reward_cap_points)}</b>.
            </Typography.Paragraph>
          </Card>
        </Space>
      )}
    </div>
  );
}
