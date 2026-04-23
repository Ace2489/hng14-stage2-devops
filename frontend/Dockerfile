FROM oven/bun:1.3-alpine AS builder

WORKDIR /build

COPY package.json ./

RUN bun install --production

FROM oven/bun:alpine AS runtime

WORKDIR /app

COPY --from=builder /build/node_modules ./node_modules
COPY app.js .
COPY views/ ./views/

USER bun

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD bun -e "const r = await fetch('http://localhost:$FRONTEND_PORT/health'); if (!r.ok) process.exit(1);" || exit 1

CMD ["bun", "app.js"]
