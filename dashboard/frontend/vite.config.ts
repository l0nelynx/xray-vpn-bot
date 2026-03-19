import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/bot/dashboard/",
  server: {
    proxy: {
      "/bot/dashboard/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
