import { Routes, Route, Navigate, useLocation } from "react-router";
import { isAuthenticated } from "./api/client";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UsersPage from "./pages/UsersPage";
import TransactionsPage from "./pages/TransactionsPage";
import StatsPage from "./pages/StatsPage";
import MenuEditorPage from "./pages/MenuEditorPage";
import TelmtPage from "./pages/TelmtPage";
import StorePage from "./pages/StorePage";
import SupportPage from "./pages/SupportPage";
import WebAppTariffsPage from "./pages/WebAppTariffsPage";
import WebAppSettingsPage from "./pages/WebAppSettingsPage";
import TgAdminPage from "./pages/TgAdminPage";
import CrmPage from "./pages/crm/CrmPage";
import PromocodesPage from "./pages/PromocodesPage";
import GiveawaysPage from "./pages/GiveawaysPage";
import PushPage from "./pages/push/PushPage";
import ApiHealthPage from "./pages/ApiHealthPage";

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
