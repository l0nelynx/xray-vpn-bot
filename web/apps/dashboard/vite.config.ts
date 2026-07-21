import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "XRAY Dashboard",
        short_name: "Dashboard",
        description: "VPN Admin Dashboard",
        start_url: "/bot/dashboard/",
        scope: "/bot/dashboard/",
        display: "standalone",
        background_color: "#0C0F1A",
        theme_color: "#0C0F1A",
        icons: [
          {
            src: "pwa-192x192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-maskable-192x192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "maskable",
          },
          {
            src: "pwa-maskable-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "/bot/dashboard/index.html",
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/bot/dashboard/api"),
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
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
