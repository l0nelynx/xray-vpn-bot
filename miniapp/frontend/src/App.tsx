import { Navigate, Route, Routes } from "react-router-dom";
import BottomTabs from "./components/BottomTabs";
import { useMe } from "./hooks/useMe";
import HomePage from "./pages/HomePage";
import SettingsPage from "./pages/SettingsPage";
import SupportCreatePage from "./pages/SupportCreatePage";
import SupportPage from "./pages/SupportPage";
import SupportTicketPage from "./pages/SupportTicketPage";
import WelcomePage from "./pages/WelcomePage";

export default function App() {
  const { data, loading, error, reload } = useMe();

  if (loading) {
    return <div className="spinner-wrap">Загрузка…</div>;
  }

  if (error) {
    return (
      <div className="page">
        <div className="error-banner">
          {error === "username required"
            ? "Установите username в настройках Telegram, чтобы пользоваться сервисом."
            : `Ошибка: ${error}`}
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="spinner-wrap">Нет данных</div>;
  }

  if (!data.registered) {
    return <WelcomePage links={data.links} />;
  }

  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<HomePage me={data} reload={reload} />} />
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
