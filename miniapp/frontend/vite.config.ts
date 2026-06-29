import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/bot/miniapp/",
  server: {
    proxy: {
      "/bot/miniapp/api": "http://localhost:8001",
    },
  },
  build: {
    outDir: "dist",
  },
});
