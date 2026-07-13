import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntApp } from "antd";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { liquidGlassConfig } from "./theme/liquidGlass";
import "./theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename="/bot/dashboard">
      <ConfigProvider {...liquidGlassConfig}>
        <AntApp>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>
);
