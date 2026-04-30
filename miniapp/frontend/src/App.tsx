import { ConfigProvider, Result, Spin, Alert } from "antd";
import { useEffect, useState } from "react";
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
import useIllustrationTheme from "./theme/illustrationTheme";

interface AppInnerProps {
  themeMode: "light" | "dark";
  onToggleTheme: () => void;
}

function AppInner({ themeMode, onToggleTheme }: AppInnerProps) {
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
        <Alert type="warning" message="Нет данных" />
      </div>
    );
  }

  if (!data.registered) {
    return <WelcomePage links={data.links} />;
  }

  return (
    <div className="app with-theme-toggle">
      <button
        type="button"
        className="theme-toggle"
        onClick={onToggleTheme}
      >
        {themeMode === "light" ? "Тёмная" : "Светлая"}
      </button>
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
  const [themeMode, setThemeMode] = useState<"light" | "dark">("light");

  useEffect(() => {
    document.body.classList.toggle("theme-dark", themeMode === "dark");
  }, [themeMode]);

  const configProps = useIllustrationTheme(themeMode);
  return (
    <ConfigProvider {...configProps}>
      <AppInner
        themeMode={themeMode}
        onToggleTheme={() =>
          setThemeMode((prev) => (prev === "light" ? "dark" : "light"))
        }
      />
    </ConfigProvider>
  );
}
