import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout as AntLayout, Menu, Button, Drawer, theme } from "antd";
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
} from "@ant-design/icons";
import { clearToken } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";

const { Sider, Header, Content } = AntLayout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/users", icon: <UserOutlined />, label: "Users" },
  { key: "/transactions", icon: <TransactionOutlined />, label: "Transactions" },
  { key: "/stats", icon: <BarChartOutlined />, label: "Statistics" },
  { key: "/tariffs", icon: <ShoppingOutlined />, label: "Tariffs" },
  { key: "/menus", icon: <AppstoreOutlined />, label: "Bot Menus" },
  { key: "/squads", icon: <TeamOutlined />, label: "Squads" },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const isMobile = useIsMobile();

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  const handleMenuClick = (key: string) => {
    navigate(key);
    if (isMobile) setMobileMenuOpen(false);
  };

  const sidebarContent = (
    <>
      <div
        style={{
          height: 56,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: isMobile ? 18 : collapsed ? 14 : 18,
          color: token.colorPrimary,
          letterSpacing: isMobile ? 2 : collapsed ? 0 : 2,
          borderBottom: "1px solid rgba(255,255,255,0.04)",
        }}
      >
        {!isMobile && collapsed ? "VP" : "XRAY VPN"}
      </div>
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={({ key }) => handleMenuClick(key)}
        style={{
          borderRight: 0,
          background: "transparent",
          padding: "8px 4px",
        }}
      />
      {isMobile && (
        <div style={{ padding: "16px", marginTop: "auto" }}>
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            block
            style={{ color: "rgba(255,255,255,0.5)", textAlign: "left" }}
          >
            Logout
          </Button>
        </div>
      )}
    </>
  );

  return (
    <AntLayout style={{ minHeight: "100vh", background: "#0a0a0f" }}>
      {/* Desktop sidebar */}
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          trigger={null}
          width={240}
          collapsedWidth={64}
          style={{
            background: "#0f0f18",
            borderRight: "1px solid rgba(255,255,255,0.04)",
            overflow: "auto",
            height: "100vh",
            position: "sticky",
            top: 0,
            left: 0,
          }}
        >
          {sidebarContent}
        </Sider>
      )}

      {/* Mobile drawer menu */}
      {isMobile && (
        <Drawer
          placement="left"
          open={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          width={260}
          closeIcon={<CloseOutlined style={{ color: "rgba(255,255,255,0.6)" }} />}
          styles={{
            header: { display: "none" },
            body: {
              padding: 0,
              background: "#0f0f18",
              display: "flex",
              flexDirection: "column",
            },
          }}
          rootStyle={{ zIndex: 1001 }}
        >
          {sidebarContent}
        </Drawer>
      )}

      <AntLayout style={{ background: "#0a0a0f" }}>
        <Header
          style={{
            padding: isMobile ? "0 12px" : "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(15,15,24,0.8)",
            backdropFilter: "blur(12px)",
            borderBottom: "1px solid rgba(255,255,255,0.04)",
            height: 56,
            lineHeight: "56px",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          {isMobile ? (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setMobileMenuOpen(true)}
              style={{ color: "rgba(255,255,255,0.6)" }}
            />
          ) : (
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ color: "rgba(255,255,255,0.6)" }}
            />
          )}
          {isMobile ? (
            <span
              style={{
                fontWeight: 700,
                fontSize: 16,
                color: token.colorPrimary,
                letterSpacing: 1,
              }}
            >
              XRAY VPN
            </span>
          ) : null}
          {!isMobile ? (
            <Button
              type="text"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              style={{ color: "rgba(255,255,255,0.5)" }}
            >
              Logout
            </Button>
          ) : (
            <div style={{ width: 32 }} /> // Spacer for centering title
          )}
        </Header>
        <Content
          style={{
            margin: isMobile ? 12 : 24,
            minHeight: "calc(100vh - 56px - 48px)",
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
