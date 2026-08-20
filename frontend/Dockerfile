# Build stage — compile the Vite app to static assets.
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked in at build time (Vite inlines import.meta.env at compile time).
# Left empty so the built app calls the API/WebSocket via same-origin
# relative paths — Caddy routes those to the backend, so the same image
# works unmodified behind any DOMAIN (see Caddyfile).
ARG VITE_API_URL=""
ARG VITE_WS_URL=""
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

RUN npm run build

# Serve stage — nginx serving the static build with SPA fallback.
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

EXPOSE 80
