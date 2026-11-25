FROM node:24.22.3-bookworm-slim@sha256:873f586f3794f52281bd039bf02c048a0be08fde619338f9941bad1eb6b34530 AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS dependencies
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM base AS builder
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN --network=none npm run build

FROM base AS runtime
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
COPY --from=builder --chown=node:node /app/.next/standalone ./
USER node
EXPOSE 3000
CMD ["node", "server.js"]
