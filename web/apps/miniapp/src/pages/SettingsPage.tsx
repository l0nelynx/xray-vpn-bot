import {
  Check,
  ChevronRight,
  FileText,
  Gift,
  Languages,
  Link2,
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
import { useLocale } from "../i18n/LocaleContext";
import { translate, type Locale } from "../i18n";
import { POINTS_ICON, formatPoints } from "../points";
import { showAlert } from "../tg/webapp";
import StackPageHeader from "../components/StackPageHeader";

interface Props {
  username: string;
  hasEmail: boolean;
  email: string | null;
}

interface SettingsItemDef {
  key: string;
  icon: React.ReactNode;
  label: string;
  badge?: React.ReactNode;
  onClick: () => void;
}

const LANG_OPTIONS: Locale[] = ["ru", "en"];

export default function SettingsPage({ username, hasEmail, email }: Props) {
  const navigate = useNavigate();
  const { t, locale, setLocale } = useLocale();
  const [promoState, setPromoState] = useState<PromoState | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [inputCode, setInputCode] = useState("");
  const [activating, setActivating] = useState(false);
  const [savingLang, setSavingLang] = useState(false);

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
      toast.success(
        t("settings.promo.toastSuccess", {
          grant: formatPoints(res.credit_grant),
          balance: formatPoints(res.balance),
        })
      );
    } catch (e: unknown) {
      showAlert(e instanceof Error ? e.message : t("settings.promo.errorFallback"));
    } finally {
      setActivating(false);
    }
  };

  const handleLanguage = async (next: Locale) => {
    if (next === locale || savingLang) return;
    setSavingLang(true);
    try {
      await setLocale(next);
      toast.success(translate(next, "settings.language.toastSaved"));
    } catch {
      toast.error(translate(locale, "settings.language.toastFailed"));
    } finally {
      setSavingLang(false);
    }
  };

  const referralItems: SettingsItemDef[] = [
    {
      key: "invite",
      icon: <UserPlus />,
      label: t("settings.inviteFriends"),
      onClick: () => navigate("/invite", { state: { returnTo: "/settings" } }),
    },
    {
      key: "rules",
      icon: <Users />,
      label: t("settings.referralRules"),
      onClick: () => navigate("/referral-rules"),
    },
  ];

  const legalItems: SettingsItemDef[] = [
    {
      key: "policy",
      icon: <Shield />,
      label: t("settings.privacy"),
      onClick: () => navigate("/policy"),
    },
    {
      key: "agreement",
      icon: <FileText />,
      label: t("settings.agreement"),
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
      <StackPageHeader title={t("settings.title")} backTo="/" />

      {username && (
        <div className="flex items-center justify-between bg-card border border-border rounded-2xl px-4 py-3.5 mb-3">
          <span className="text-muted-foreground text-sm">{t("settings.telegram")}</span>
          <Badge>@{username}</Badge>
        </div>
      )}

      {hasEmail && email ? (
        <div className="flex items-center justify-between gap-3 bg-card border border-border rounded-2xl px-4 py-3.5 mb-3">
          <span className="text-muted-foreground text-sm">{t("settings.email")}</span>
          <Badge className="max-w-[70%] truncate font-normal normal-case tracking-normal">
            {email}
          </Badge>
        </div>
      ) : (
        <button className="email-recovery-card mb-3" onClick={() => navigate("/account/link?returnTo=%2Fsettings")}>
          <Link2 />
          <span><strong>{t("settings.linkEmail.title")}</strong><small>{t("settings.linkEmail.body")}</small></span>
          <ChevronRight />
        </button>
      )}

      {(promoState?.balance ?? 0) > 0 && (
        <div className="flex items-center justify-between gap-3 bg-card border border-border rounded-2xl px-4 py-3.5 mb-3">
          <span className="text-muted-foreground text-sm">{t("settings.bonusBalance")}</span>
          <Badge variant="success">
            {formatPoints(promoState!.balance)}
          </Badge>
        </div>
      )}

      <div className="settings-section mb-3">
        <div className="settings-item" style={{ cursor: "default" }}>
          <div className="settings-item__icon">
            <Languages />
          </div>
          <span className="settings-item__text">{t("settings.language")}</span>
          <div className="settings-language-options flex gap-1.5 ml-auto">
            {LANG_OPTIONS.map((code) => {
              const active = locale === code;
              return (
                <button
                  key={code}
                  type="button"
                  disabled={savingLang}
                  onClick={() => handleLanguage(code)}
                  className={
                    "inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium border transition-colors " +
                    (active
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-transparent text-muted-foreground border-border")
                  }
                >
                  {active && <Check className="size-3" />}
                  {t(`settings.language.${code}`)}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="settings-section mb-3">
        <button
          className="settings-item"
          onClick={() => setModalOpen(true)}
        >
          <div className="settings-item__icon">
            <Gift />
          </div>
          <span className="settings-item__text">{t("settings.activatePromo")}</span>
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

      <Dialog open={modalOpen} onOpenChange={(open: boolean) => { setModalOpen(open); if (!open) setInputCode(""); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("settings.promo.modalTitle")}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-1">
            <p className="text-muted-foreground m-0 text-sm">
              {t("settings.promo.modalBody", { icon: POINTS_ICON })}
            </p>
            <Input
              placeholder={t("settings.promo.placeholder")}
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
              {activating ? t("settings.promo.applying") : t("settings.promo.apply")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
