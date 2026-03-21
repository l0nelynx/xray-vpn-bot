import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout as AntLayout, Menu, Button, theme } from "antd";
import {
  DashboardOutlined,
  UserOutlined,
  TransactionOutlined,
  BarChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { clearToken } from "../api/client";

const { Sider, Header, Content } = AntLayout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/users", icon: <UserOutlined />, label: "Users" },
  { key: "/transactions", icon: <TransactionOutlined />, label: "Transactions" },
  { key: "/stats", icon: <BarChartOutlined />, label: "Statistics" },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  return (
    <AntLayout style={{ minHeight: "100vh", background: "#0a0a0f" }}>
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
        <div
          style={{
            height: 56,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: collapsed ? 14 : 18,
            color: token.colorPrimary,
            letterSpacing: collapsed ? 0 : 2,
            borderBottom: "1px solid rgba(255,255,255,0.04)",
          }}
        >
          {collapsed ? "VP" : "XRAY VPN"}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            borderRight: 0,
            background: "transparent",
            padding: "8px 4px",
          }}
        />
      </Sider>
      <AntLayout style={{ background: "#0a0a0f" }}>
        <Header
          style={{
            padding: "0 24px",
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
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ color: "rgba(255,255,255,0.6)" }}
          />
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            style={{ color: "rgba(255,255,255,0.5)" }}
          >
            Logout
          </Button>
        </Header>
        <Content style={{ margin: 24, minHeight: "calc(100vh - 56px - 48px)" }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
