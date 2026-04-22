# Bug Fixes

---

## 1. Data Integrity

### Race Condition on Job Creation
**File**: `api/main.py`, original lines 14–15

The job ID was pushed onto the queue before its status hash was written. The worker could dequeue the job in the window between the two operations, find no status key, and either skip it or overwrite a status the API had not yet set.

**Before**:
```python
r.lpush("job", job_id)
r.hset(f"job:{job_id}", "status", "queued")
```

**After** (`api/main.py`, lines 35–39): Wrapped in a pipeline so all three operations (hash set, TTL, queue push) are sent to Redis atomically. The worker cannot dequeue the job before its hash exists.
```python
pipe = r.pipeline()
pipe.hset(f"job:{job_id}", "status", "queued")
pipe.expire(f"job:{job_id}", 86400)
pipe.lpush("job", job_id)
pipe.execute()
```

---

### No Intermediate "Processing" Status
**File**: `worker/main.py`, original lines 8–12

Jobs transitioned directly from `queued` to `completed` with nothing in between. There was no way to distinguish a job that was waiting in the queue from one that was actively running.

**Before**:
```python
def process_job(job_id):
    print(f"Processing job {job_id}")
    time.sleep(2)
    r.hset(f"job:{job_id}", "status", "completed")
```

**After** (`worker/main.py`, lines 39–51): Status is set to `processing` immediately on dequeue, before any work begins.
```python
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
```

---

## 2. Error Handling & Resilience

### Unhandled Exceptions Kill the Worker Loop
**File**: `worker/main.py`, original lines 17–21

Any exception raised inside `process_job` propagated out of the `while True` loop, terminating the worker process entirely. All subsequent jobs were silently abandoned.

**Before**:
```python
while True:
    job = r.brpop("job", timeout=5)
    if job:
        _, job_id = job
        process_job(job_id.decode())
```

**After** (`worker/main.py`, lines 67–73): Exceptions are caught per-job. The failed job's status is set to `failed`, it is recorded in a dead-letter queue for later inspection, and the loop continues.
```python
try:
    process_job(job_id.decode())
except Exception as e:
    log.error(f"Job {job_id} failed: {e}")

    r.hset(f"job:{job_id}", "status", "failed")
    r.expire(f"job:{job_id}", 86400)
    r.lpush(DEAD_LETTER_QUEUE, job_id)
```

---

### No "Failed" Status Written on Error
**File**: `worker/main.py`

Related to the above: even if exceptions had been caught, there was no code path that ever set a job's status to `failed`. Jobs that errored would remain stuck as `queued` or `processing` forever, with no signal to the caller that anything went wrong.

**Fix**: The `except` block in the updated worker (lines 72–73) now explicitly sets `status` to `failed` and resets the TTL.

---

### Worker Does Not Shut Down Gracefully
**File**: `worker/main.py`

A `SIGTERM` would cause the process to exit immediately, potentially mid-job. The job would be lost, as it was already off the queue, but not yet completed.

**After** (`worker/main.py`, lines 26–36): A `shutdown` flag is set by signal handlers for both `SIGTERM` and `SIGINT`. The main loop checks the flag on each iteration, finishing the current job before exiting.
```python
shutdown = False

def handle_signal(signum, frame):
    global shutdown
    log.info(f"Received signal {signum}, will quit after current job")
    shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

while not shutdown:
    ...
```

---

### Wrong HTTP Status Code for Missing Job
**File**: `api/main.py`, original lines 23–24

Returning a plain dictionary from a FastAPI route produces HTTP `200 OK` regardless of content, i.e. a missing job was returned the same HTTP code as a found one.

**Before**:
```python
if not status:
    return {"error": "not found"}
```

**After** (`api/main.py`, lines 47–48):
```python
if not status:
    raise HTTPException(status_code=404, detail="job not found")
```

---

## 3. Configuration & Security

### Hardcoded Redis Host and API URL
**Files**: `api/main.py` original line 8, `worker/main.py` original line 6, `frontend/app.js` original line 6

Connection parameters were hardcoded to `localhost`, which is incorrect in any containerised or networked environment.

**Before**:
```python
r = redis.Redis(host="localhost", port=6379)
```
```js
const API_URL = "http://localhost:8000";
```

**After** — all three services now read from environment variables with no fallback for required values:

`api/main.py` and `worker/main.py` (lines 9–13, 16–21):
```python
def require_env(key) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set")
    return value

r = redis.Redis(
    host=require_env("REDIS_HOST"),
    port=int(require_env("REDIS_PORT"),
    password=require_env("REDIS_PASSWORD"),
    decode_responses=True,
)
```

`frontend/app.js` (lines 5–7):
```js
const API_URL = process.env.API_URL;
const PORT = parseInt(process.env.PORT);
const REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS);
```

---

### No Redis Authentication
**Files**: `api/main.py` original line 8, `worker/main.py` original line 6

Redis was connected without a password. Any process on the same network could read or write the job queue.

**Fix**: Both services now pass `password=require_env("REDIS_PASSWORD")` in the connection constructor (see above).

---

### `.env` File Tracked in Git
**File**: `api/.env`

The `.env` file containing local credentials was committed to the repository, potentially leaking secrets.

**Fix**: `.env` removed from version control and added to `.gitignore`. A `.env.example` with placeholder values is committed in its place.

---

## 4. Observability

### No Structured Logging
**Files**: `api/main.py`, `worker/main.py`

The worker used `print()` statements. The API had no logging at all. Neither produced timestamps or log levels, making it difficult to correlate events or diagnose issues in production.

**After** — worker (`worker/main.py`, lines 23–24):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout
)
log = logging.getLogger(__name__)
```

All `print()` calls replaced with `log.info()` / `log.error()`. API structured logging to be added in a follow-up.

---

### No Health Check Endpoints
**Files**: `api/main.py`, `frontend/app.js`

Neither service exposed a health endpoint, making them opaque to orchestrators and `docker-compose` dependency health checks.

**After** — API (`api/main.py`, lines 24–25):
```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

Frontend (`frontend/app.js`, line 12):
```js
app.get("/health", (req, res) => res.json({ status: "ok" }));
```

Worker exposes health via a Redis heartbeat key rather than an HTTP endpoint (`worker/main.py`, lines 54–55):
```python
def report_healthy():
    r.set("worker:heartbeat", "1", ex=30)
```

---

### No Error Logging in Frontend
**File**: `frontend/app.js`, original lines 15–17, 24–26

Caught exceptions were swallowed — only a generic message was returned to the client with no record of what actually failed.

**Before**:
```js
} catch (err) {
  res.status(500).json({ error: "something went wrong" });
}
```

**After** (`frontend/app.js`, lines 22–24):
```js
} catch (err) {
  console.error("[POST /submit]", err.message);
  res.status(500).json({ error: "something went wrong" });
}
```

---

## 5. Resource Management

### Unbounded Redis Key Growth
**File**: `api/main.py`, original line 14

Job hash keys were never expired. Under sustained load, Redis memory grows without bound.

**Before**:
```python
r.hset(f"job:{job_id}", "status", "queued")
```

**After** (`api/main.py`, lines 36–37): A 24-hour TTL is set immediately alongside the hash write.
```python
pipe.hset(f"job:{job_id}", "status", "queued")
pipe.expire(f"job:{job_id}", 86400)
```

The worker also resets the TTL on each status transition so long-running jobs do not expire mid-flight.

---

### No Timeout on Upstream API Calls
**File**: `frontend/app.js`, original lines 13, 22

Axios requests to the FastAPI service had no timeout. A slow or unresponsive API would cause the Express handler to hang indefinitely, eventually exhausting the Node.js event loop.

**Before**:
```js
const response = await axios.post(`${API_URL}/jobs`);
```

**After** (`frontend/app.js`, lines 16–20):
```js
const response = await axios.post(
  `${API_URL}/jobs`,
  {},
  { timeout: REQUEST_TIMEOUT_MS },
);
```
