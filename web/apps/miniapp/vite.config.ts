import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "/bot/miniapp/",
  server: {
    proxy: {
      ...(mode === "mock" ? { "/bot/miniapp/api/support": "http://127.0.0.1:8790" } : {}),
      "/bot/miniapp/api": "http://localhost:8001",
    },
  },
  build: {
    outDir: "dist",
  },
}));
