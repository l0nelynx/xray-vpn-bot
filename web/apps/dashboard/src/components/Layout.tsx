import { useState, useEffect, useMemo } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout as AntLayout, Menu, Button, Drawer, Popconfirm } from "antd";
import type { MenuProps } from "antd";
import {
  DashboardOutlined,
  UserOutlined,
  TransactionOutlined,
  BarChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
  CloseOutlined,
  ShoppingOutlined,
  AppstoreOutlined,
  TeamOutlined,
  CloudServerOutlined,
  ShopOutlined,
  MessageOutlined,
  MobileOutlined,
  GiftOutlined,
  CustomerServiceOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { api, clearToken } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";

const { Sider, Content } = AntLayout;

type ItemType = NonNullable<MenuProps["items"]>[number];

const PAGE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/users": "Users",
  "/transactions": "Transactions",
  "/stats": "Statistics",
  "/tariffs": "Tariffs",
  "/menus": "Bot Menus",
  "/squads": "Squads",
  "/telemt": "Telemt",
  "/store": "Store",
  "/support": "Support",
  "/promocodes": "Promocodes",
  "/webapp/tariffs": "Tariff Constructor",
  "/webapp/settings": "Settings",
  "/tg-admin": "TG Admin",
  "/crm": "CRM",
};

function buildMenuItems(legacyEnabled: boolean): ItemType[] {
  const legacyGroup: ItemType[] = legacyEnabled
    ? [
        {
          type: "group",
          label: "Bot Constructor",
          key: "g-bot",
          children: [
            { key: "/tariffs", icon: <ShoppingOutlined />, label: "Tariffs" },
            { key: "/menus", icon: <AppstoreOutlined />, label: "Bot Menus" },
            { key: "/squads", icon: <TeamOutlined />, label: "Squads" },
          ],
        } as ItemType,
      ]
    : [];

  return [
    {
      type: "group",
      label: "Overview",
      key: "g-overview",
      children: [
        { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
        { key: "/users", icon: <UserOutlined />, label: "Users" },
        { key: "/transactions", icon: <TransactionOutlined />, label: "Transactions" },
        { key: "/stats", icon: <BarChartOutlined />, label: "Statistics" },
      ],
    } as ItemType,
    ...legacyGroup,
    {
      type: "group",
      label: "Services",
      key: "g-services",
      children: [
        { key: "/telemt", icon: <CloudServerOutlined />, label: "Telemt" },
        { key: "/store", icon: <ShopOutlined />, label: "Store" },
        { key: "/support", icon: <MessageOutlined />, label: "Support" },
        { key: "/promocodes", icon: <GiftOutlined />, label: "Promocodes" },
        { key: "/crm", icon: <CustomerServiceOutlined />, label: "CRM" },
        { key: "/tg-admin", icon: <RobotOutlined />, label: "TG Admin" },
      ],
    } as ItemType,
    {
      type: "group",
      label: "WebApp",
      key: "g-webapp",
      children: [
        {
          key: "webapp",
          icon: <MobileOutlined />,
          label: "WebApp",
          children: [
            { key: "/webapp/tariffs", label: "Tariff Constructor" },
            { key: "/webapp/settings", label: "Settings" },
          ],
        },
      ],
    } as ItemType,
  ];
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [legacyEnabled, setLegacyEnabled] = useState<boolean>(true);
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobile();

  useEffect(() => {
    api
      .get<{ legacy_bot_constructor: boolean }>("/settings/features")
      .then((r) => setLegacyEnabled(r.legacy_bot_constructor))
      .catch(() => setLegacyEnabled(true));
  }, []);

  const menuItems = useMemo(() => buildMenuItems(legacyEnabled), [legacyEnabled]);

  const [openKeys, setOpenKeys] = useState<string[]>(() =>
    location.pathname.startsWith("/webapp") ? ["webapp"] : [],
  );

  useEffect(() => {
    if (location.pathname.startsWith("/webapp")) {
      setOpenKeys((keys) => (keys.includes("webapp") ? keys : [...keys, "webapp"]));
    }
  }, [location.pathname]);

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    if (!key.startsWith("/")) return;
    navigate(key);
    if (isMobile) setMobileMenuOpen(false);
  };

  const pageTitle = PAGE_TITLES[location.pathname] ?? "Dashboard";

  /* ── Sidebar content ──────────────────────────────── */
  const sidebarContent = (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Logo */}
      <div
        style={{
          height: 56,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          borderBottom: "1px solid #1A2038",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: "linear-gradient(135deg, #6C8EFF, #A78BFF)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 700,
            color: "#fff",
            flexShrink: 0,
          }}
        >
          VP
        </div>
        {(!collapsed || isMobile) && (
          <span
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "#E2E8F8",
              letterSpacing: 0.3,
              whiteSpace: "nowrap",
              overflow: "hidden",
            }}
          >
            VPN Admin
          </span>
        )}
      </div>

      {/* Nav */}
      <div style={{ flex: 1, overflow: "auto", paddingTop: 6 }}>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[location.pathname]}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ background: "transparent", border: 0 }}
        />
      </div>

      {/* Footer logout */}
      <div
        style={{
          padding: "12px 10px",
          borderTop: "1px solid #1A2038",
          flexShrink: 0,
        }}
      >
        <Popconfirm
          title="Log out?"
          description="You will need to sign in again."
          onConfirm={handleLogout}
          okText="Logout"
          cancelText="Cancel"
          placement="top"
        >
          <Button
            type="text"
            icon={<LogoutOutlined />}
            aria-label="Logout"
            style={{
              width: "100%",
              textAlign: "left",
              color: "rgba(255,255,255,0.35)",
              fontSize: 13,
              height: 34,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {(!collapsed || isMobile) && "Logout"}
          </Button>
        </Popconfirm>
      </div>
    </div>
  );

  return (
    <AntLayout style={{ minHeight: "100vh", background: "#0C0F1A" }}>
      {/* Desktop sidebar */}
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          trigger={null}
          width={220}
          collapsedWidth={60}
          style={{
            background: "#0F1220",
            borderRight: "1px solid #1A2038",
            overflow: "hidden",
            height: "100vh",
            position: "sticky",
            top: 0,
            left: 0,
          }}
        >
          {sidebarContent}
        </Sider>
      )}

      {/* Mobile drawer */}
      {isMobile && (
        <Drawer
          placement="left"
          open={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          width={240}
          closeIcon={<CloseOutlined style={{ color: "rgba(255,255,255,0.5)" }} />}
          styles={{
            header: { display: "none" },
            body: { padding: 0, background: "#0F1220", display: "flex", flexDirection: "column" },
          }}
          rootStyle={{ zIndex: 1001 }}
        >
          {sidebarContent}
        </Drawer>
      )}

      <AntLayout style={{ background: "#0C0F1A", overflow: "hidden" }}>
        {/* Top bar */}
        <div
          style={{
            height: 52,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: isMobile ? "0 14px" : "0 20px",
            background: "#0F1220",
            borderBottom: "1px solid #1A2038",
            position: "sticky",
            top: 0,
            zIndex: 10,
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* Toggle / burger */}
            <Button
              type="text"
              aria-label={isMobile ? "Open navigation menu" : collapsed ? "Expand sidebar" : "Collapse sidebar"}
              icon={
                isMobile ? (
                  <MenuOutlined />
                ) : collapsed ? (
                  <MenuUnfoldOutlined />
                ) : (
                  <MenuFoldOutlined />
                )
              }
              onClick={isMobile ? () => setMobileMenuOpen(true) : () => setCollapsed(!collapsed)}
              style={{ color: "rgba(255,255,255,0.40)", padding: 0, width: 32, height: 32 }}
            />
            {/* Page title */}
            <span
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: "#E2E8F8",
                letterSpacing: -0.1,
              }}
            >
              {pageTitle}
            </span>
          </div>

          {/* Breadcrumb path — subtle */}
          <span
            style={{
              fontSize: 11.5,
              color: "rgba(255,255,255,0.22)",
              letterSpacing: 0.2,
              display: isMobile ? "none" : "block",
            }}
          >
            {location.pathname === "/" ? "/ dashboard" : location.pathname}
          </span>
        </div>

        {/* Page content */}
        <Content
          style={{
            padding: isMobile ? 12 : 20,
            minHeight: "calc(100vh - 52px)",
            overflow: "auto",
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
