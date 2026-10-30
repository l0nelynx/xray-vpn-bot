# Build context for this Dockerfile is the repository root.
# Use:  docker build -f infra/docker/frontend.Dockerfile .
#
# Static web tier: builds BOTH SPAs (npm workspaces) and serves them with nginx.
# All routing (static vs API vs webhooks) is owned by the edge nginx — this
# container does not proxy to the backends. See README "Web tier & reverse proxy".

# Stage 1: build both frontends from the workspace.
# bookworm (glibc) avoids Alpine/musl optional-native gaps when the lockfile
# was generated on Windows/macOS (npm/cli#4828 — rollup/lightningcss/oxide).
FROM node:22.23.4-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS build
WORKDIR /build
COPY package.json package-lock.json ./
COPY web/apps/dashboard/package.json ./web/apps/dashboard/package.json
COPY web/apps/miniapp/package.json ./web/apps/miniapp/package.json
COPY web/packages/api/package.json ./web/packages/api/package.json
COPY web/packages/ui/package.json ./web/packages/ui/package.json
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY web ./web
# TypeScript checks the mock handlers too; they import the shared app catalog.
COPY services/miniapp/backend/connect/app_config.default.json ./services/miniapp/backend/connect/app_config.default.json
RUN npm run build -w xray-vpn-dashboard \
 && npm run build -w xray-vpn-miniapp

# Stage 2: nginx serving the built assets + proxying to backends.
FROM nginx:1.30.6-alpine@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949
RUN apk upgrade --no-cache
COPY infra/docker/frontend.nginx.conf /etc/nginx/nginx.conf
COPY --from=build /build/web/apps/dashboard/dist /usr/share/nginx/html/bot/dashboard
COPY --from=build /build/web/apps/miniapp/dist   /usr/share/nginx/html/bot/miniapp

EXPOSE 80
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/bot/miniapp/ >/dev/null 2>&1 || exit 1
