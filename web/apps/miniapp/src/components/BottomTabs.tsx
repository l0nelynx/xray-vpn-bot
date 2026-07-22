import { Home, Laptop, MessageCircle, Settings } from "lucide-react";
import { useLocation, useNavigate } from "react-router";

const TABS = [
  { path: "/", icon: <Home />, label: "Главная" },
  { path: "/devices", icon: <Laptop />, label: "Устройства" },
  { path: "/support", icon: <MessageCircle />, label: "Поддержка" },
  { path: "/settings", icon: <Settings />, label: "Аккаунт" },
];

export default function BottomTabs() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname.startsWith(path);
  };

  return (
    <nav className="bottom-tabs">
      {TABS.map((tab) => (
        <button
          key={tab.path}
          className={isActive(tab.path) ? "active" : ""}
          onClick={() => navigate(tab.path)}
        >
          <span className="icon">{tab.icon}</span>
          <span className="label">{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
