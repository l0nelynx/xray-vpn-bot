import { Routes, Route, Navigate } from "react-router-dom";
import { isAuthenticated } from "./api/client";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UsersPage from "./pages/UsersPage";
import TransactionsPage from "./pages/TransactionsPage";
import StatsPage from "./pages/StatsPage";
import TariffEditorPage from "./pages/TariffEditorPage";
import MenuEditorPage from "./pages/MenuEditorPage";
import SquadProfilesPage from "./pages/SquadProfilesPage";
import TelmtPage from "./pages/TelmtPage";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
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
        <Route path="tariffs" element={<TariffEditorPage />} />
        <Route path="menus" element={<MenuEditorPage />} />
        <Route path="squads" element={<SquadProfilesPage />} />
        <Route path="telemt" element={<TelmtPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
