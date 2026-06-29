# Build context for this Dockerfile is the repository root.
# Use:  docker build -f infra/docker/frontend.Dockerfile .
#
# Single web tier: builds BOTH SPAs (npm workspaces) and serves them with nginx,
# reverse-proxying API/webhook traffic to the backend service containers.

# Stage 1: build both frontends from the workspace.
FROM node:20-alpine AS build
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
