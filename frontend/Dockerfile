FROM node:22-alpine AS builder
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
# Ensure public/ exists even if the directory isn't tracked
RUN mkdir -p public

# Pass backend URL at build time if needed (leave blank → frontend derives it
# from window.location at runtime, which works for any hostname/IP automatically)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN pnpm build

# ── Runtime stage (only the standalone bundle, no node_modules bloat) ─────────
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production PORT=3100 HOSTNAME=0.0.0.0

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3100
CMD ["node", "server.js"]
