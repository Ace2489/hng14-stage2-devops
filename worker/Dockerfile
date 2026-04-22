FROM python:3.12-alpine AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip==latest \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-alpine

WORKDIR /app

COPY --from=builder /install /usr/local

RUN addgroup -S worker \
 && adduser -S -G worker -H -D worker

COPY worker.py healthcheck.py ./

USER worker

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "healthcheck.py"]

CMD ["python", "worker.py"]
