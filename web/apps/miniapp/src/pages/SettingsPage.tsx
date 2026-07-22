import {
  ChevronRight,
  FileText,
  Gift,
  Shield,
  Users,
  UserPlus,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import { PromoState, promo as promoApi } from "../api/client";
import { POINTS_ICON, formatPoints } from "../points";
import { showAlert } from "../tg/webapp";

interface Props {
  username: string;
}

interface SettingsItemDef {
  key: string;
  icon: React.ReactNode;
  label: string;
  badge?: React.ReactNode;
  onClick: () => void;
}

export default function SettingsPage({ username }: Props) {
  const navigate = useNavigate();
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
      toast.success(`+${formatPoints(res.credit_grant)} на баланс (всего ${formatPoints(res.balance)})`);
    } catch (e: unknown) {
      showAlert(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setActivating(false);
    }
  };

  const referralItems: SettingsItemDef[] = [
    {
      key: "invite",
      icon: <UserPlus />,
      label: "Пригласить друзей",
      onClick: () => navigate("/invite"),
    },
    {
      key: "rules",
      icon: <Users />,
      label: "Правила реферальной программы",
      onClick: () => navigate("/referral-rules"),
    },
  ];

  const legalItems: SettingsItemDef[] = [
    {
      key: "policy",
      icon: <Shield />,
      label: "Политика конфиденциальности",
      onClick: () => navigate("/policy"),
    },
    {
      key: "agreement",
      icon: <FileText />,
      label: "Пользовательское соглашение",
      onClick: () => navigate("/agreement"),
    },
  ];

  const renderSection = (items: SettingsItemDef[]) => (
    <div className="settings-section">
      {items.map((item) => (
        <button key={item.key} className="settings-item" onClick={item.onClick}>
          <div className="settings-item__icon">{item.icon}</div>
          <span className="settings-item__text">{item.label}</span>
          {item.badge && <span>{item.badge}</span>}
          <ChevronRight className="settings-item__arrow" />
        </button>
      ))}
    </div>
  );

  return (
    <div className="page">
      <div className="text-[22px] font-bold text-foreground tracking-tight mb-5">
        Аккаунт
      </div>

      {/* User chip */}
      {username && (
        <div className="flex items-center justify-between bg-card border border-border rounded-2xl px-4 py-3.5 mb-3">
          <span className="text-muted-foreground text-sm">Telegram</span>
          <Badge>@{username}</Badge>
        </div>
      )}

      {(promoState?.balance ?? 0) > 0 && (
        <div className="flex items-center justify-between gap-3 bg-card border border-border rounded-2xl px-4 py-3.5 mb-3">
          <span className="text-muted-foreground text-sm">Бонусный баланс</span>
          <Badge variant="success">
            {formatPoints(promoState!.balance)}
          </Badge>
        </div>
      )}

      <div className="settings-section mb-3">
        <button
          className="settings-item"
          onClick={() => setModalOpen(true)}
        >
          <div className="settings-item__icon">
            <Gift />
          </div>
          <span className="settings-item__text">Активировать промокод</span>
          {(promoState?.balance ?? 0) > 0 && (
            <Badge className="text-[11px]">
              {formatPoints(promoState!.balance)}
            </Badge>
          )}
          <ChevronRight className="settings-item__arrow" />
        </button>
      </div>

      {renderSection(referralItems)}
      {renderSection(legalItems)}

      {/* Promo modal */}
      <Dialog open={modalOpen} onOpenChange={(open: boolean) => { setModalOpen(open); if (!open) setInputCode(""); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Активировать промокод</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-1">
            <p className="text-muted-foreground m-0 text-sm">
              Введите промокод — баллы {POINTS_ICON} начислятся на баланс сразу
            </p>
            <Input
              placeholder="EXAMPLE123"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && handleActivate()}
              maxLength={20}
              autoFocus
            />
            <Button
              size="lg"
              className="w-full"
              disabled={activating || !inputCode.trim()}
              onClick={handleActivate}
            >
              {activating ? "Применяем…" : "Применить"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
