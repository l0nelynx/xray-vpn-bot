import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/bot/dashboard/",
  server: {
//    host: "127.0.0.1",
//    port: 5173,
    proxy: {
        "/bot/dashboard/api": "http://localhost:8000",
//      "/bot/dashboard/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
