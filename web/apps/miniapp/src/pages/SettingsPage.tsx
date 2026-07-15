import {
  FileTextOutlined,
  GiftOutlined,
  RightOutlined,
  SafetyOutlined,
  TeamOutlined,
  UsergroupAddOutlined,
} from "@ant-design/icons";
import { Button, Input, Modal, Space, Tag, App } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PromoState, promo as promoApi } from "../api/client";
import { POINTS_ICON, formatPoints } from "../points";
import { showAlert } from "../tg/webapp";

interface Props {
  username: string;
}

interface SettingsItemDef {
  key: string;
  icon: React.ReactNode;
  iconBg: string;
  label: string;
  badge?: React.ReactNode;
  onClick: () => void;
}

export default function SettingsPage({ username }: Props) {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [promoState, setPromoState] = useState<PromoState | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [inputCode, setInputCode] = useState("");
  const [activating, setActivating] = useState(false);

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
          ? { ...prev, balance: res.balance, last_promo_code: res.promo_code }
          : { balance: res.balance, last_promo_code: res.promo_code, default_credit_grant: 10 }
      );
      setModalOpen(false);
      setInputCode("");
      message.success(`+${formatPoints(res.credit_grant)} на баланс (всего ${formatPoints(res.balance)})`);
    } catch (e: unknown) {
      showAlert(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setActivating(false);
    }
  };

  const referralItems: SettingsItemDef[] = [
    {
      key: "invite",
      icon: <UsergroupAddOutlined />,
      iconBg: "rgba(124,156,255,0.15)",
      label: "Пригласить друзей",
      onClick: () => navigate("/invite"),
    },
    {
      key: "rules",
      icon: <TeamOutlined />,
      iconBg: "rgba(124,156,255,0.15)",
      label: "Правила реферальной программы",
      onClick: () => navigate("/referral-rules"),
    },
  ];

  const legalItems: SettingsItemDef[] = [
    {
      key: "policy",
      icon: <SafetyOutlined />,
      iconBg: "rgba(78,203,168,0.15)",
      label: "Политика конфиденциальности",
      onClick: () => navigate("/policy"),
    },
    {
      key: "agreement",
      icon: <FileTextOutlined />,
      iconBg: "rgba(78,203,168,0.15)",
      label: "Пользовательское соглашение",
      onClick: () => navigate("/agreement"),
    },
  ];

  const renderSection = (items: SettingsItemDef[]) => (
    <div className="settings-section">
      {items.map((item) => (
        <button key={item.key} className="settings-item" onClick={item.onClick}>
          <div
            className="settings-item__icon"
            style={{ background: item.iconBg, color: "rgba(255,255,255,0.80)" }}
          >
            {item.icon}
          </div>
          <span className="settings-item__text">{item.label}</span>
          {item.badge && <span>{item.badge}</span>}
          <RightOutlined className="settings-item__arrow" />
        </button>
      ))}
    </div>
  );

  return (
    <div className="page">
      <div style={{ fontSize: 22, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px", marginBottom: 20 }}>
        Аккаунт
      </div>

      {/* User chip */}
      {username && (
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.10)",
          borderRadius: 16,
          padding: "14px 16px",
          marginBottom: 12,
        }}>
          <span style={{ color: "rgba(255,255,255,0.45)", fontSize: 14 }}>Telegram</span>
          <Tag color="processing" style={{ margin: 0, fontWeight: 600 }}>@{username}</Tag>
        </div>
      )}

      {(promoState?.balance ?? 0) > 0 && (
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "rgba(78,203,168,0.10)",
          border: "1px solid rgba(78,203,168,0.28)",
          borderRadius: 16,
          padding: "14px 16px",
          marginBottom: 12,
          gap: 12,
        }}>
          <span style={{ color: "rgba(255,255,255,0.60)", fontSize: 14 }}>Бонусный баланс</span>
          <Tag color="success" style={{ margin: 0, fontWeight: 600 }}>
            {formatPoints(promoState!.balance)}
          </Tag>
        </div>
      )}

      <div className="settings-section" style={{ marginBottom: 12 }}>
        <button
          className="settings-item"
          onClick={() => setModalOpen(true)}
        >
          <div
            className="settings-item__icon"
            style={{ background: "rgba(255,212,121,0.15)", color: "#FFD479" }}
          >
            <GiftOutlined />
          </div>
          <span className="settings-item__text">Активировать промокод</span>
          {(promoState?.balance ?? 0) > 0 && (
            <Tag color="processing" style={{ margin: 0, fontSize: 11 }}>
              {formatPoints(promoState!.balance)}
            </Tag>
          )}
          <RightOutlined className="settings-item__arrow" />
        </button>
      </div>

      {renderSection(referralItems)}
      {renderSection(legalItems)}

      {/* Promo modal */}
      <Modal
        title="Активировать промокод"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setInputCode(""); }}
        footer={null}
        centered
      >
        <Space direction="vertical" size={12} style={{ width: "100%", paddingTop: 4 }}>
          <p style={{ color: "rgba(255,255,255,0.50)", margin: 0, fontSize: 14 }}>
            Введите промокод — баллы {POINTS_ICON} начислятся на баланс сразу
          </p>
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
