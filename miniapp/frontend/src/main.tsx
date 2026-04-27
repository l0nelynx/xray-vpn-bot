import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { initTelegram } from "./tg/webapp";
import "./theme.css";

initTelegram();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename="/bot/miniapp">
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
