import { AlertTriangle } from "lucide-react";
import { Spinner } from "@xray/ui/components/spinner";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { useCallback } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { me as meApi, type MeResponse } from "./api/client";
import BottomTabs from "./components/BottomTabs";
import { useMe } from "./hooks/useMe";
import { LocaleProvider, useT } from "./i18n/LocaleContext";
import { normalizeLocale, type Locale } from "./i18n";
import BuyMenuPage from "./pages/BuyMenuPage";
import BuySuccessPage from "./pages/BuySuccessPage";
import ConnectPage from "./pages/ConnectPage";
import DevicesPage from "./pages/DevicesPage";
import FreeTrialPage from "./pages/FreeTrialPage";
import AgreementPage from "./pages/AgreementPage";
import HomePage from "./pages/HomePage";
import InvitePage from "./pages/InvitePage";
import PolicyPage from "./pages/PolicyPage";
import ReferralRulesPage from "./pages/ReferralRulesPage";
import SettingsPage from "./pages/SettingsPage";
import SubscriptionsPage from "./pages/SubscriptionsPage";
import SupportCreatePage from "./pages/SupportCreatePage";
import SupportPage from "./pages/SupportPage";
import SupportTicketPage from "./pages/SupportTicketPage";
import WelcomePage from "./pages/WelcomePage";
import AccountLinkPage from "./pages/AccountLinkPage";
import OnboardingPage, { ONBOARDING_VERSION } from "./pages/OnboardingPage";

function AppRoutes({
  data,
  loading,
  error,
  reload,
  refresh,
}: {
  data: MeResponse | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<MeResponse | null>;
  refresh: () => Promise<MeResponse | null>;
}) {
  const { t } = useT();
  const { pathname } = useLocation();

  if (loading) {
    return (
      <div className="spinner-wrap">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page page-centered">
        <div style={{ textAlign: "center", maxWidth: 320 }}>
          <AlertTriangle
            style={{ width: 48, height: 48, color: "#FF8A8A", margin: "0 auto 16px" }}
          />
          <div style={{ fontSize: 18, fontWeight: 700, color: "#FFFFFF", marginBottom: 8 }}>
            {t("app.error.genericTitle")}
          </div>
          <div style={{ fontSize: 14, color: "rgba(255,255,255,0.52)", lineHeight: 1.5 }}>
            {error}
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <Alert variant="warning">
          <AlertTitle>{t("app.error.noData")}</AlertTitle>
        </Alert>
      </div>
    );
  }

  if (!data.registered) {
    return <WelcomePage links={data.links} />;
  }

  const onboardingRequired = (data.user?.onboarding_version ?? 0) < ONBOARDING_VERSION;
  const onboardingRoute = pathname === "/onboarding" || pathname === "/account/link";
  if (onboardingRequired && !onboardingRoute) {
    return <Navigate to="/onboarding" replace />;
  }

  const showTabs = pathname === "/" || pathname === "/connect" || pathname === "/buy" || pathname === "/support";

  return (
    <div className={`app ${/^\/support\/\d+$/.test(pathname) ? "support-chat-shell" : ""}`}>
      <Routes>
        <Route path="/" element={<HomePage me={data} reload={reload} refresh={refresh} />} />
        <Route path="/buy" element={<BuyMenuPage />} />
        <Route path="/buy/success" element={<BuySuccessPage />} />
        <Route path="/connect" element={<ConnectPage />} />
        <Route path="/onboarding" element={<OnboardingPage me={data} reload={reload} />} />
        <Route path="/account/link" element={<AccountLinkPage hasEmail={Boolean(data.user?.has_email)} email={data.user?.email || null} reload={reload} />} />
        <Route path="/subscriptions" element={<SubscriptionsPage refresh={refresh} />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/free/:mode" element={<FreeTrialPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/support/new" element={<SupportCreatePage />} />
        <Route path="/support/:id" element={<SupportTicketPage />} />
        <Route
          path="/settings"
          element={
            <SettingsPage
              username={data.user?.username || ""}
              hasEmail={Boolean(data.user?.has_email)}
              email={data.user?.email || null}
            />
          }
        />
        <Route path="/invite" element={<InvitePage />} />
        <Route path="/policy" element={<PolicyPage links={data.links} />} />
        <Route path="/referral-rules" element={<ReferralRulesPage />} />
        <Route path="/agreement" element={<AgreementPage links={data.links} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {showTabs && <BottomTabs />}
    </div>
  );
}

function AppInner() {
  const { data, loading, error, reload, refresh, setUserLanguage } = useMe();

  const onLocaleChange = useCallback(async (locale: Locale) => {
    const updated = await meApi.setLanguage(locale);
    setUserLanguage(normalizeLocale(updated.language));
  }, [setUserLanguage]);

  const locale = normalizeLocale(data?.user?.language);

  return (
    <LocaleProvider locale={locale} onLocaleChange={onLocaleChange}>
      <AppRoutes
        data={data}
        loading={loading}
        error={error}
        reload={reload}
        refresh={refresh}
      />
    </LocaleProvider>
  );
}

export default function App() {
  return <AppInner />;
}
