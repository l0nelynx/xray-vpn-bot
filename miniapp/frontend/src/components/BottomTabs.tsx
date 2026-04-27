import { useLocation, useNavigate } from "react-router-dom";

const TABS = [
  { path: "/", icon: "🏠", label: "Главная" },
  { path: "/support", icon: "💬", label: "Поддержка" },
  { path: "/settings", icon: "⚙️", label: "Аккаунт" },
];

export default function BottomTabs() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname.startsWith(path);
  };

  return (
    <div className="bottom-tabs">
      {TABS.map((tab) => (
        <button
          key={tab.path}
          className={isActive(tab.path) ? "active" : ""}
          onClick={() => navigate(tab.path)}
        >
          <span className="icon">{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
}
