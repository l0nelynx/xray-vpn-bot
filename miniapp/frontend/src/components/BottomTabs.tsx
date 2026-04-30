import {
  HomeOutlined,
  LaptopOutlined,
  MessageOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";

const TABS = [
  { path: "/", icon: <HomeOutlined />, label: "Главная" },
  { path: "/devices", icon: <LaptopOutlined />, label: "Устройства" },
  { path: "/support", icon: <MessageOutlined />, label: "Поддержка" },
  { path: "/settings", icon: <SettingOutlined />, label: "Аккаунт" },
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
