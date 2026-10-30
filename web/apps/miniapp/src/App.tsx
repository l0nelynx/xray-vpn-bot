import { AlertTriangle } from "lucide-react";
import { Spinner } from "@xray/ui/components/spinner";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { lazy, Suspense, useCallback } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { me as meApi, type MeResponse } from "./api/client";
import BottomTabs from "./components/BottomTabs";
import RemnawaveMaintenance from "./components/RemnawaveMaintenance";
import { useMe } from "./hooks/useMe";
import { LocaleProvider, useT } from "./i18n/LocaleContext";
import { normalizeLocale, type Locale } from "./i18n";
import { tg } from "./tg/webapp";
import HomePage from "./pages/HomePage";
import OnboardingPage, { ONBOARDING_VERSION } from "./pages/OnboardingPage";

const BuyMenuPage = lazy(() => import("./pages/BuyMenuPage"));
const BuySuccessPage = lazy(() => import("./pages/BuySuccessPage"));
const ConnectPage = lazy(() => import("./pages/ConnectPage"));
const DevicesPage = lazy(() => import("./pages/DevicesPage"));
const FreeTrialPage = lazy(() => import("./pages/FreeTrialPage"));
const AgreementPage = lazy(() => import("./pages/AgreementPage"));
const InvitePage = lazy(() => import("./pages/InvitePage"));
const PolicyPage = lazy(() => import("./pages/PolicyPage"));
const ReferralRulesPage = lazy(() => import("./pages/ReferralRulesPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const SubscriptionsPage = lazy(() => import("./pages/SubscriptionsPage"));
const SupportCreatePage = lazy(() => import("./pages/SupportCreatePage"));
const SupportPage = lazy(() => import("./pages/SupportPage"));
const SupportTicketPage = lazy(() => import("./pages/SupportTicketPage"));
const WelcomePage = lazy(() => import("./pages/WelcomePage"));
const AccountLinkPage = lazy(() => import("./pages/AccountLinkPage"));

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
            {t(error === "remnawave_unavailable" ? "maintenance.title" : "app.error.genericTitle")}
          </div>
          <div style={{ fontSize: 14, color: "rgba(255,255,255,0.52)", lineHeight: 1.5 }}>
            {error === "remnawave_unavailable" ? t("subscriptions.unavailable") : error}
          </div>
          {error === "remnawave_unavailable" && (
            <Button className="mt-4" variant="outline" onClick={() => void reload()}>{t("home.refreshAria")}</Button>
          )}
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
      <Suspense fallback={<div className="spinner-wrap" role="status" aria-label="Loading"><Spinner className="h-8 w-8" /></div>}>
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
      </Suspense>
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

  const locale = normalizeLocale(data?.user?.language ?? tg?.initDataUnsafe?.user?.language_code);

  return (
    <LocaleProvider locale={locale} onLocaleChange={onLocaleChange}>
      <RemnawaveMaintenance onRecovered={() => { void refresh(); }} subscriptionStatus={data?.subscription?.status} />
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
