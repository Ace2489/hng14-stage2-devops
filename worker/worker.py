import logging
import os
import signal
import time

import redis


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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

shutdown = False


def handle_signal(signum, frame):
    global shutdown
    log.info(f"Received signal {signum}, will quit after current job")
    shutdown = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def process_job(job_id):
    log.info(f"Processing job {job_id}")

    pipe = r.pipeline()
    pipe.hset(f"job:{job_id}", "status", "processing")
    pipe.expire(f"job:{job_id}", 86400)
    pipe.execute()

    time.sleep(2)  # simulate work

    r.hset(f"job:{job_id}", "status", "completed")
    r.expire(f"job:{job_id}", 86400)
    log.info(f"Done: {job_id}")


def report_healthy():
    r.set("worker:heartbeat", "1", ex=30)


DEAD_LETTER_QUEUE = "job:dead"  # Fix #16

log.info("Worker service running")
while not shutdown:
    job = r.brpop("job", timeout=5)

    if job is None:
        report_healthy()
        continue

    _, job_id = job

    try:
        process_job(job_id)
    except Exception as e:
        log.error(f"Job {job_id} failed: {e}")

        r.hset(f"job:{job_id}", "status", "failed")
        r.expire(f"job:{job_id}", 86400)
        r.lpush(DEAD_LETTER_QUEUE, job_id)

    report_healthy()
