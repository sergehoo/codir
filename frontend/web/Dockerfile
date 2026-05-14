# ─── Build (Vite) ────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_API_BASE
ARG VITE_FRONTEND_URL
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_FRONTEND_URL=${VITE_FRONTEND_URL}

# Copie package.json et lockfile si présent
COPY package.json ./
COPY package-lock.json* ./

# Utilise `npm ci` si lockfile présent (reproductible), sinon fallback `npm install`
RUN if [ -f package-lock.json ]; then \
      npm ci --no-audit --no-fund; \
    else \
      echo "WARN: pas de package-lock.json — fallback npm install" && \
      npm install --no-audit --no-fund; \
    fi

COPY . .
RUN npm run build

# ─── Runtime (Nginx interne) ─────────────────────────
FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/codir-web.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
