import logging
import os
import sys

import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

try:
    r = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ["REDIS_PORT"]),
        password=os.environ["REDIS_PASSWORD"],
        decode_responses=True,
        socket_connect_timeout=3,
    )
    alive = r.get("worker:heartbeat")
    sys.exit(0 if alive else 1)
except Exception as e:
    logging.error(f"error failed: {e}")
    sys.exit(1)
