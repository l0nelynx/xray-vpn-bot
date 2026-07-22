import { Home, Laptop, MessageCircle, Settings } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { useT } from "../i18n/LocaleContext";

const TABS = [
  { path: "/", icon: <Home />, labelKey: "tabs.home" },
  { path: "/devices", icon: <Laptop />, labelKey: "tabs.devices" },
  { path: "/support", icon: <MessageCircle />, labelKey: "tabs.support" },
  { path: "/settings", icon: <Settings />, labelKey: "tabs.account" },
] as const;

export default function BottomTabs() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { t } = useT();

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
          <span className="label">{t(tab.labelKey)}</span>
        </button>
      ))}
    </nav>
  );
}
