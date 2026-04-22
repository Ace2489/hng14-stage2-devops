import os
import uuid

import redis
from fastapi import FastAPI, HTTPException


def require_env(key) -> str:
    value = os.getenv(key)
    if value is None:
        raise RuntimeError(f"Required environment variable '{key}' is not set")
    return value


r = redis.Redis(
    host=require_env("REDIS_HOST"),
    port=int(require_env("REDIS_PORT")),
    password=require_env("REDIS_PASSWORD"),
    decode_responses=True,
)

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())

    pipe = r.pipeline()
    pipe.hset(f"job:{job_id}", "status", "queued")
    pipe.expire(f"job:{job_id}", 86400)
    pipe.lpush("job", job_id)
    pipe.execute()

    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = r.hget(f"job:{job_id}", "status")
    if not status:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "status": status}
