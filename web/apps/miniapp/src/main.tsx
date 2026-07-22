import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router";
import { Toaster } from "@xray/ui/components/sonner";
import App from "./App";
import { initTelegram } from "./tg/webapp";
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
    console.info("[mock] MSW enabled — miniapp API is mocked (no Telegram needed)");
  }
  initTelegram();
}

prepare().then(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <BrowserRouter basename="/bot/miniapp">
        <App />
        <Toaster />
      </BrowserRouter>
    </React.StrictMode>,
  );
});
