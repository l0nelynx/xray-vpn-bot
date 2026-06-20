import { App, Avatar, Button, Layout, Menu, Typography } from "antd";
import {
  LaptopOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  ShoppingCartOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import BrandLogo from "../components/BrandLogo";
import { BRAND_NAME } from "../branding";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import SubscriptionTab from "./dashboard/SubscriptionTab";
import BuyTab from "./dashboard/BuyTab";
import DevicesTab from "./dashboard/DevicesTab";
import SettingsTab from "./dashboard/SettingsTab";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

type TabKey = "subscription" | "buy" | "devices" | "settings";

const MENU_ITEMS = [
  { key: "subscription", icon: <WifiOutlined />, label: "Подписка" },
  { key: "buy", icon: <ShoppingCartOutlined />, label: "Купить" },
  { key: "devices", icon: <LaptopOutlined />, label: "Устройства" },
  { key: "settings", icon: <SafetyCertificateOutlined />, label: "Настройки" },
];

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("subscription");
  const [collapsed, setCollapsed] = useState(false);

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  function renderTab() {
    switch (tab) {
      case "subscription":
        return <SubscriptionTab onBuyClick={() => setTab("buy")} />;
      case "buy":
        return <BuyTab />;
      case "devices":
        return <DevicesTab />;
      case "settings":
        return <SettingsTab />;
    }
  }

  return (
    <App>
      <Layout style={{ minHeight: "100vh", background: "#0B0B14" }}>
        {/* ── Sidebar ────────────────────────────────────────────────────── */}
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          breakpoint="md"
          width={220}
          style={{
            background: "rgba(255,255,255,0.03)",
            borderRight: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          {/* Logo */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: collapsed ? "20px 18px" : "20px 24px",
              borderBottom: "1px solid rgba(255,255,255,0.07)",
              overflow: "hidden",
              transition: "padding 0.2s",
            }}
          >
            <BrandLogo size={32} style={{ flexShrink: 0 }} />
            {!collapsed && (
              <Text strong style={{ color: "#fff", fontSize: 15, whiteSpace: "nowrap" }}>
                {BRAND_NAME.split(" ")[0]}
              </Text>
            )}
          </div>

          {/* Navigation */}
          <Menu
            mode="inline"
            selectedKeys={[tab]}
            items={MENU_ITEMS}
            onClick={({ key }) => setTab(key as TabKey)}
            style={{
              background: "transparent",
              border: "none",
              padding: "12px 0",
            }}
            theme="dark"
          />

          {/* Logout at bottom */}
          <div
            style={{
              position: "absolute",
              bottom: 60,
              width: "100%",
              padding: collapsed ? "0 12px" : "0 12px",
            }}
          >
            <Button
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              block
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "rgba(255,255,255,0.5)",
                borderRadius: 10,
                textAlign: "left",
              }}
            >
              {!collapsed && "Выйти"}
            </Button>
          </div>
        </Sider>

        {/* ── Main ───────────────────────────────────────────────────────── */}
        <Layout style={{ background: "#0B0B14" }}>
          {/* Header */}
          <Header
            style={{
              background: "rgba(255,255,255,0.02)",
              borderBottom: "1px solid rgba(255,255,255,0.07)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 32px",
              height: 60,
            }}
          >
            <Text style={{ color: "rgba(255,255,255,0.5)", fontSize: 14 }}>
              Клиентский портал
            </Text>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Avatar
                size={32}
                style={{ background: "linear-gradient(135deg, #06D6A0, #0096C7)", fontSize: 14 }}
              >
                {(user?.email || "U")[0].toUpperCase()}
              </Avatar>
              <Text style={{ color: "rgba(255,255,255,0.7)", fontSize: 14 }}>
                {user?.email || "—"}
              </Text>
            </div>
          </Header>

          {/* Content */}
          <Content
            style={{
              padding: "32px 40px",
              overflowY: "auto",
              maxWidth: 1100,
              width: "100%",
            }}
          >
            {renderTab()}
          </Content>
        </Layout>
      </Layout>
    </App>
  );
}
