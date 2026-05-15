# ─── Build (Vite) ────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_API_BASE
ARG VITE_FRONTEND_URL
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_FRONTEND_URL=${VITE_FRONTEND_URL}

# Outils pour les natives optionnelles (esbuild, etc.)
RUN apk add --no-cache python3 make g++ git

# Copie tout le manifest + lockfile éventuel
COPY package.json ./
COPY package-lock.json* ./

# Installation tolérante :
#  - legacy-peer-deps : ignore les conflits peer (Tiptap, React 18, etc.)
#  - no-audit / no-fund : pas de bruit
#  - prefer-offline : si déjà en cache
RUN npm config set fund false && \
    npm config set audit false && \
    npm install --legacy-peer-deps --no-audit --no-fund --prefer-offline

# Build
COPY . .
RUN npm run build

# ─── Runtime (Nginx interne) ─────────────────────────
FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/codir-web.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
