import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme } from "antd";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename="/bot/dashboard">
      <ConfigProvider
        theme={{
          algorithm: theme.darkAlgorithm,
          token: {
            colorPrimary: "#4f8cff",
            colorBgBase: "#0a0a0f",
            colorBgContainer: "#13131d",
            colorBgElevated: "#1a1a28",
            colorBorderSecondary: "rgba(255,255,255,0.06)",
            colorBorder: "rgba(255,255,255,0.08)",
            colorText: "rgba(255,255,255,0.88)",
            colorTextSecondary: "rgba(255,255,255,0.55)",
            colorTextTertiary: "rgba(255,255,255,0.4)",
            borderRadius: 10,
            fontSize: 14,
          },
          components: {
            Card: {
              colorBgContainer: "#13131d",
              headerBg: "transparent",
              colorTextHeading: "rgba(255,255,255,0.88)",
            },
            Table: {
              colorBgContainer: "#13131d",
              headerBg: "#181828",
              headerColor: "rgba(255,255,255,0.65)",
              colorText: "rgba(255,255,255,0.8)",
              borderColor: "rgba(255,255,255,0.06)",
              rowHoverBg: "rgba(79,140,255,0.06)",
            },
            Menu: {
              darkItemBg: "transparent",
              darkSubMenuItemBg: "transparent",
              darkItemSelectedBg: "rgba(79,140,255,0.15)",
              darkItemHoverBg: "rgba(255,255,255,0.06)",
              darkItemColor: "rgba(255,255,255,0.55)",
              darkItemSelectedColor: "#4f8cff",
            },
            Input: {
              colorBgContainer: "#1a1a28",
              colorBorder: "rgba(255,255,255,0.1)",
            },
            Select: {
              colorBgContainer: "#1a1a28",
              colorBorder: "rgba(255,255,255,0.1)",
            },
            Button: {
              colorBgTextHover: "rgba(255,255,255,0.06)",
            },
            Statistic: {
              colorTextDescription: "rgba(255,255,255,0.5)",
              colorTextHeading: "rgba(255,255,255,0.95)",
            },
            Descriptions: {
              colorTextLabel: "rgba(255,255,255,0.55)",
              colorText: "rgba(255,255,255,0.85)",
            },
            Drawer: {
              colorBgElevated: "#1a1a28",
            },
          },
        }}
      >
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>
);
