# syntax=docker/dockerfile:1.7

# ---------- Builder stage ----------
FROM node:20-alpine AS builder

ENV CI=true \
    PNPM_HOME=/root/.local/share/pnpm \
    PATH="/root/.local/share/pnpm:$PATH"

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_URL
ARG VITE_ENV=production
ENV VITE_API_URL=$VITE_API_URL \
    VITE_ENV=$VITE_ENV

RUN pnpm build

# ---------- Runtime stage ----------
FROM nginx:1.27-alpine AS runtime

RUN addgroup -S app && adduser -S -G app app

COPY --from=builder /app/dist /usr/share/nginx/html

RUN printf 'server {\n\
  listen 80;\n\
  server_name _;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  location / {\n\
    try_files $uri $uri/ /index.html;\n\
  }\n\
  location = /healthz {\n\
    access_log off;\n\
    add_header Content-Type text/plain;\n\
    return 200 "ok";\n\
  }\n\
  gzip on;\n\
  gzip_types text/plain text/css application/javascript application/json image/svg+xml;\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
