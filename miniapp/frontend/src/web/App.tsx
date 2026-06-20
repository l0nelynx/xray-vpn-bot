import { ConfigProvider, Spin } from "antd";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { LangProvider } from "./locale";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import DashboardPage from "./pages/DashboardPage";
import { webThemeConfig } from "./theme/webTheme";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#0B0B14",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spin size="large" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireVerified({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.email_verified) return <Navigate to="/verify-email" replace />;
  return <>{children}</>;
}

export default function WebApp() {
  return (
    <LangProvider>
    <ConfigProvider {...webThemeConfig}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/verify-email"
          element={
            <RequireAuth>
              <VerifyEmailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RequireVerified>
              <DashboardPage />
            </RequireVerified>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ConfigProvider>
    </LangProvider>
  );
}
