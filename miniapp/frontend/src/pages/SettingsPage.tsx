import {
  FileTextOutlined,
  GiftOutlined,
  KeyOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { Button, Card, Input, Modal, Space, Tag, Typography, theme, message } from "antd";
import { useEffect, useState } from "react";
import { LinksInfo, PromoState, promo as promoApi } from "../api/client";
import { openLink, showAlert } from "../tg/webapp";

interface Props {
  links: LinksInfo;
  username: string;
}

export default function SettingsPage({ links, username }: Props) {
  const { token } = theme.useToken();
  const [promoState, setPromoState] = useState<PromoState | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [inputCode, setInputCode] = useState("");
  const [activating, setActivating] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    promoApi.getState().then(setPromoState).catch(() => {});
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
      key: "policy",
      icon: <SafetyOutlined />,
      title: "Политика конфиденциальности",
      onClick: () => openLink(links.policy_url),
    },
    {
      key: "agreement",
      icon: <FileTextOutlined />,
      title: "Пользовательское соглашение",
      onClick: () => openLink(links.agreement_url),
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
        <Card size="small" style={{ marginBottom: 16, borderColor: token.colorSuccess }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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
            style={{
              height: "auto",
              minHeight: token.controlHeightLG,
              paddingInline: 16,
              paddingBlock: 12,
              justifyContent: "flex-start",
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              {item.icon}
              <span>{item.title}</span>
            </span>
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
    </div>
  );
}
