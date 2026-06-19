import {
  FileTextOutlined,
  GiftOutlined,
  KeyOutlined,
  SafetyOutlined,
  TeamOutlined,
  UsergroupAddOutlined,
} from "@ant-design/icons";
import { Button, Card, Input, Modal, Space, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  PromoState,
  ReferralState,
  promo as promoApi,
  referral as referralApi,
} from "../api/client";
import { showAlert } from "../tg/webapp";

interface Props {
  username: string;
}

export default function SettingsPage({ username }: Props) {
  const navigate = useNavigate();
  const [promoState, setPromoState] = useState<PromoState | null>(null);
  const [referralState, setReferralState] = useState<ReferralState | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [inputCode, setInputCode] = useState("");
  const [activating, setActivating] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    promoApi.getState().then(setPromoState).catch(() => {});
    referralApi.getState().then(setReferralState).catch(() => {});
  }, []);

  const handleActivate = async () => {
    const code = inputCode.trim().toUpperCase();
    if (!code) return;
    setActivating(true);
    try {
      const res = await promoApi.activate(code);
      setPromoState((prev) =>
        prev
          ? {
              ...prev,
              can_activate: false,
              active_promo: res.active_promo,
              discount_percent: res.discount_percent,
            }
          : prev
      );
      setModalOpen(false);
      setInputCode("");
      messageApi.success(`Промокод ${res.active_promo} активирован — скидка ${res.discount_percent}%`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Ошибка";
      showAlert(msg);
    } finally {
      setActivating(false);
    }
  };

  const items = [
    {
      key: "invite",
      icon: <UsergroupAddOutlined />,
      title: "Пригласить друзей",
      onClick: () => navigate("/invite"),
    },
    {
      key: "rules",
      icon: <TeamOutlined />,
      title: "Правила реферальной программы",
      onClick: () => setRulesOpen(true),
    },
    {
      key: "policy",
      icon: <SafetyOutlined />,
      title: "Политика конфиденциальности",
      onClick: () => navigate("/policy"),
    },
    {
      key: "agreement",
      icon: <FileTextOutlined />,
      title: "Пользовательское соглашение",
      onClick: () => navigate("/agreement"),
    },
    {
      key: "login",
      icon: <KeyOutlined />,
      title: "Вход в аккаунт",
      onClick: () =>
        showAlert("Раздел «Вход в аккаунт» появится в следующей версии."),
    },
    {
      key: "promo",
      icon: <GiftOutlined />,
      title: promoState?.active_promo
        ? `Промокод: ${promoState.active_promo} (−${promoState.discount_percent}%)`
        : "Активировать промокод",
      onClick: () => {
        if (promoState?.active_promo) {
          showAlert(
            `Активный промокод: ${promoState.active_promo}\nСкидка: ${promoState.discount_percent}% на следующую покупку`
          );
        } else {
          setModalOpen(true);
        }
      },
    },
  ];

  return (
    <div className="page">
      {contextHolder}
      <Typography.Title level={3} style={{ marginBottom: 20 }}>
        Аккаунт
      </Typography.Title>

      {username && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Typography.Text type="secondary">Telegram</Typography.Text>
            <Tag color="processing">@{username}</Tag>
          </div>
        </Card>
      )}

      {promoState?.active_promo && (
        <Card size="small" className="glass-success" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <Typography.Text type="secondary">Скидка активна</Typography.Text>
            <Tag color="success">−{promoState.discount_percent}% на следующую покупку</Tag>
          </div>
        </Card>
      )}

      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {items.map((item) => (
          <Button
            key={item.key}
            block
            size="large"
            type={item.key === "promo" && !promoState?.active_promo ? "dashed" : "default"}
            onClick={item.onClick}
            className="settings-row"
          >
            <span className="icon">{item.icon}</span>
            <span className="text">{item.title}</span>
          </Button>
        ))}
      </Space>

      <Modal
        title="Активировать промокод"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setInputCode(""); }}
        footer={null}
        centered
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Text type="secondary">
            Введите промокод для получения скидки на первую покупку
          </Typography.Text>
          <Input
            placeholder="EXAMPLE123"
            value={inputCode}
            onChange={(e) => setInputCode(e.target.value.toUpperCase())}
            onPressEnter={handleActivate}
            maxLength={20}
            size="large"
            autoFocus
          />
          <Button
            type="primary"
            block
            size="large"
            loading={activating}
            disabled={!inputCode.trim()}
            onClick={handleActivate}
          >
            Применить
          </Button>
        </Space>
      </Modal>

      <Modal
        title="Правила реферальной программы"
        open={rulesOpen}
        onCancel={() => setRulesOpen(false)}
        footer={null}
        centered
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <b>Реферальные промокоды</b>
            <ul style={{ marginTop: 6, marginBottom: 0, paddingLeft: 18 }}>
              <li>
                У каждого пользователя есть личный промокод — поделитесь им с
                друзьями.
              </li>
              <li>
                Друг получает скидку{" "}
                <b>{referralState?.discount_percent ?? 0}%</b> на первую покупку.
              </li>
              <li>
                Реферальный промокод доступен только новым пользователям — у кого
                ещё не было покупок.
              </li>
              <li>Активировать реферальный промокод можно только один раз.</li>
            </ul>
          </Typography.Paragraph>

          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <b>Бонусы за приглашения</b>
            <ul style={{ marginTop: 6, marginBottom: 0, paddingLeft: 18 }}>
              <li>
                За каждые 30 дней, купленных по вашему коду, вы получаете{" "}
                <b>{referralState?.days_reward_per_30 ?? 0}</b> бонусных дней.
              </li>
              <li>
                Всего можно получить до{" "}
                <b>{referralState?.reward_cap_days ?? 0}</b> бонусных дней.
              </li>
            </ul>
          </Typography.Paragraph>

          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <b>Обычные промокоды</b>
            <ul style={{ marginTop: 6, marginBottom: 0, paddingLeft: 18 }}>
              <li>Доступны всем пользователям.</li>
              <li>Каждый конкретный промокод можно использовать только один раз.</li>
              <li>
                Одновременно может быть активен только один промокод — используйте
                его при оплате перед активацией следующего.
              </li>
            </ul>
          </Typography.Paragraph>
        </Space>
      </Modal>
    </div>
  );
}
