import { lazy } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router";
import { isAuthenticated } from "./api/client";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const TransactionsPage = lazy(() => import("./pages/TransactionsPage"));
const StatsPage = lazy(() => import("./pages/StatsPage"));
const MenuEditorPage = lazy(() => import("./pages/MenuEditorPage"));
const TelmtPage = lazy(() => import("./pages/TelmtPage"));
const StorePage = lazy(() => import("./pages/StorePage"));
const SupportPage = lazy(() => import("./pages/SupportPage"));
const WebAppTariffsPage = lazy(() => import("./pages/WebAppTariffsPage"));
const WebAppSettingsPage = lazy(() => import("./pages/WebAppSettingsPage"));
const TgAdminPage = lazy(() => import("./pages/TgAdminPage"));
const CrmPage = lazy(() => import("./pages/crm/CrmPage"));
const PromocodesPage = lazy(() => import("./pages/PromocodesPage"));
const GiveawaysPage = lazy(() => import("./pages/GiveawaysPage"));
const PushPage = lazy(() => import("./pages/push/PushPage"));
const ApiHealthPage = lazy(() => import("./pages/ApiHealthPage"));

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="stats" element={<StatsPage />} />
        <Route path="api-health" element={<ApiHealthPage />} />
        <Route
          path="tariffs"
          element={<Navigate to="/webapp/tariffs" replace />}
        />
        <Route path="menus" element={<MenuEditorPage />} />
        <Route
          path="squads"
          element={<Navigate to="/webapp/tariffs" replace />}
        />
        <Route path="telemt" element={<TelmtPage />} />
        <Route path="store" element={<StorePage />} />
        <Route path="support" element={<SupportPage />} />
        <Route path="promocodes" element={<PromocodesPage />} />
        <Route path="giveaways" element={<GiveawaysPage />} />
        <Route path="webapp/tariffs" element={<WebAppTariffsPage />} />
        <Route path="settings" element={<WebAppSettingsPage />} />
        <Route
          path="webapp/settings"
          element={<Navigate to="/settings" replace />}
        />
        <Route path="tg-admin" element={<TgAdminPage />} />
        <Route path="crm" element={<CrmPage />} />
        <Route path="push" element={<PushPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
