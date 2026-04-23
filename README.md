# HNG14 Stage 2 — Containerised Job Processor

Four services for a job processing system.:

| Service | Role | Exposed |
|---------|------|---------|
| `frontend` | Express/Node.js — job submission & tracking | `3000` |
| `api` | FastAPI — job creation & status | internal |
| `worker` | Python — job runner | internal |
| `redis` | Queue & state store | internal |

---

## Requirements
Docker, Git.

---

## Getting Started

```bash
git clone https://github.com/Godhanded/hng14-stage2-devops.git
cd hng14-stage2-devops
cp .env.example .env 
docker compose up -d --build
```

Services start in dependency order — each waits for its upstream health check before booting.

Check everything came up cleanly:
```bash
docker compose ps              # all four services should show (healthy)
```

Then visit **http://localhost:3000**, submit a job, and watch it move from `queued` → `processing` → `completed` in about two seconds.

---


## Unit Tests

```bash
pip install -r api/requirements.txt -r api/requirements-test.txt
python -m pytest tests/ -v --cov=. --cov-report=html -v
```

---

## CI/CD

Runs six stages for every push: `lint → test → build → security-scan → integration-test → deploy`. A failure at any stage kills the rest.

| Stage | Summary |
|-------|---------|
| **lint** | flake8, eslint, hadolint |
| **test** | pytest with mocked Redis; coverage report uploaded as artifact |
| **build** | Images built, tagged by git SHA, pushed to an in-runner registry and saved as tarballs |
| **security-scan** | Trivy checks for CRITICAL CVEs; results uploaded to GitHub Security tab |
| **integration-test** | Full stack boots in the runner, a real job is submitted and polled to completion |
| **deploy** | Main branch only — canary rolling update; new container must pass its health check before the old one is killed |
