import { ConfigProvider, Result, Spin, Alert } from "antd";
import { Navigate, Route, Routes } from "react-router-dom";
import BottomTabs from "./components/BottomTabs";
import { useMe } from "./hooks/useMe";
import BuyMenuPage from "./pages/BuyMenuPage";
import BuySuccessPage from "./pages/BuySuccessPage";
import DevicesPage from "./pages/DevicesPage";
import FreeTrialPage from "./pages/FreeTrialPage";
import HomePage from "./pages/HomePage";
import SettingsPage from "./pages/SettingsPage";
import SupportCreatePage from "./pages/SupportCreatePage";
import SupportPage from "./pages/SupportPage";
import SupportTicketPage from "./pages/SupportTicketPage";
import WelcomePage from "./pages/WelcomePage";
import { liquidGlassConfig } from "./theme/liquidGlass";

function AppInner() {
  const { data, loading, error, reload, refresh } = useMe();

  if (loading) {
    return (
      <div className="spinner-wrap">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    const isUsername = error === "username required";
    return (
      <div className="page">
        <Result
          status={isUsername ? "warning" : "error"}
          title={isUsername ? "Нужен username" : "Ошибка"}
          subTitle={
            isUsername
              ? "Установите username в настройках Telegram, чтобы пользоваться сервисом."
              : error
          }
        />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <Alert type="warning" title="Нет данных" />
      </div>
    );
  }

  if (!data.registered) {
    return <WelcomePage links={data.links} />;
  }

  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<HomePage me={data} reload={reload} refresh={refresh} />} />
        <Route path="/buy" element={<BuyMenuPage />} />
        <Route path="/buy/success" element={<BuySuccessPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/free/:mode" element={<FreeTrialPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/support/new" element={<SupportCreatePage />} />
        <Route path="/support/:id" element={<SupportTicketPage />} />
        <Route
          path="/settings"
          element={<SettingsPage links={data.links} username={data.user?.username || ""} />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <BottomTabs />
    </div>
  );
}

export default function App() {
  return (
    <ConfigProvider {...liquidGlassConfig}>
      <AppInner />
    </ConfigProvider>
  );
}
