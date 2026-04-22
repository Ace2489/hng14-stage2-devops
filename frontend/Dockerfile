FROM oven/bun:1.3-alpine AS builder

WORKDIR /build

COPY package.json bun.lock ./

RUN bun install --frozen-lockfile --production


FROM oven/bun:alpine

WORKDIR /app

COPY --from=builder /build/node_modules ./node_modules
COPY app.js .
COPY views/ ./views/

USER bun

ENV FRONTEND_PORT=3000
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:$FRONTEND_PORT/health || exit 1

CMD ["bun", "app.js"]
