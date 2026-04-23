FROM python:3.12-alpine AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip==26.0.1 \
&& pip install --no-cache-dir --prefix=/install --requirement requirements.txt

FROM python:3.12-alpine

WORKDIR /app

COPY --from=builder /install /usr/local/



RUN apk add --no-cache lsof=4.99.5-r0 procps-ng=4.0.5-r0 \
    && addgroup -S api \
    && adduser -S -G api -H -D api

COPY main.py .

USER api

ENV API_PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["sh", "-c", "wget -q --spider http://localhost:${API_PORT}/health || exit 1"]

CMD ["sh", "-c" ,"uvicorn main:app --host 0.0.0.0 --port ${API_PORT}"]
