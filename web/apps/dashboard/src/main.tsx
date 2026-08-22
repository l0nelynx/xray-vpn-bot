import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router";
import { registerSW } from "virtual:pwa-register";
import { Toaster } from "@xray/ui/components/sonner";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { BrandingProvider } from "./branding";
import "./index.css";
import "./theme.css";

async function prepare() {
  if (import.meta.env.VITE_MOCK_API === "1") {
    const { worker } = await import("./mocks/browser");
    await worker.start({
      onUnhandledRequest: "bypass",
      serviceWorker: {
        url: `${import.meta.env.BASE_URL}mockServiceWorker.js`,
      },
      quiet: true,
    });
    console.info("[mock] MSW enabled — dashboard API is mocked");
    return;
  }
  registerSW({ immediate: true });
}

prepare().then(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <BrowserRouter basename="/bot/dashboard">
        <BrandingProvider>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
          <Toaster />
        </BrandingProvider>
      </BrowserRouter>
    </React.StrictMode>,
  );
});
