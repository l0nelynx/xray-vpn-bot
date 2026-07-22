# Build context for this Dockerfile is the repository root.
# Use:  docker build -f infra/docker/frontend.Dockerfile .
#
# Static web tier: builds BOTH SPAs (npm workspaces) and serves them with nginx.
# All routing (static vs API vs webhooks) is owned by the edge nginx — this
# container does not proxy to the backends. See README "Web tier & reverse proxy".

# Stage 1: build both frontends from the workspace.
# bookworm (glibc) avoids Alpine/musl optional-native gaps when the lockfile
# was generated on Windows/macOS (npm/cli#4828 — rollup/lightningcss/oxide).
FROM node:22-bookworm-slim AS build
WORKDIR /build
COPY package.json package-lock.json* ./
COPY web ./web
RUN npm ci || npm install
RUN npm run build -w xray-vpn-dashboard \
 && npm run build -w xray-vpn-miniapp

# Stage 2: nginx serving the built assets + proxying to backends.
FROM nginx:1.27-alpine
COPY infra/docker/frontend.nginx.conf /etc/nginx/nginx.conf
COPY --from=build /build/web/apps/dashboard/dist /usr/share/nginx/html/bot/dashboard
COPY --from=build /build/web/apps/miniapp/dist   /usr/share/nginx/html/bot/miniapp

EXPOSE 80
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/bot/miniapp/ >/dev/null 2>&1 || exit 1
