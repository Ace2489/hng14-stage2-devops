#!/usr/bin/env bash
set -euo pipefail

IMAGE_BASE="localhost:5000"
SHA="latest"

HEALTH_TIMEOUT=60

log() { echo "[deploy] $(date +%T) $*"; }

# ── Helpers ───────────────────────────────────────────────────────────────────

# Returns all networks as --network flags
get_network_args() {
  docker inspect "$1" \
    --format='{{range $k,$_ := .NetworkSettings.Networks}}--network {{$k}} {{end}}' \
    2>/dev/null || true
}

# For logging, get them newline-separated
get_networks_display() {
  docker inspect "$1" \
    --format='{{range $k,$_ := .NetworkSettings.Networks}}{{$k}}\n{{end}}' \
    2>/dev/null | grep -v '^$'
}

# Pull an image from a registry, but fall back silently if the registry is
# unreachable and the image already exists in the local Docker store.
pull_or_use_local() {
  local image="$1"
  if docker pull "$image" 2>/dev/null; then
    log "  Pulled $image"
    return 0
  fi
  if docker image inspect "$image" &>/dev/null; then
    log "  Registry unreachable — using locally cached image: $image"
    return 0
  fi
  log "  ERROR: '$image' is not in the local store and cannot be pulled"
  return 1
}

# Block until the container reports "healthy" or until HEALTH_TIMEOUT elapses.
wait_healthy() {
  local container="$1"
  local elapsed=0
  while [ "$elapsed" -lt "$HEALTH_TIMEOUT" ]; do
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null \
             || echo "none")
    log "  health($container): $status  (${elapsed}s)"
    if [ "$status" = "healthy" ]; then
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  log "  health($container): timed out after ${HEALTH_TIMEOUT}s"
  return 1
}

# ── Core rolling-update function ──────────────────────────────────────────────

deploy_service() {
  local svc="$1"
  local image="${IMAGE_BASE}/${svc}:${SHA}"
  local old="$svc"
  local canary="${svc}_canary"

  log "=== Rolling update: $svc → $image ==="

  # Remove any stale canary left from a previous failed deploy
  if docker inspect "$canary" &>/dev/null; then
    log "  WARNING: stale canary '$canary' found — removing"
    docker rm -f "$canary"
  fi

  pull_or_use_local "$image"
  local network_args
  network_args=$(get_network_args "$old")

  if [ -z "$network_args" ]; then
    log "  ERROR: could not determine Docker network for '$old'"
    exit 1
  fi

  log "  Networks: $(get_networks_display "$old" | tr '\n' ' ')"

  # Capture the environment variables from the running container so the
  # canary starts with identical configuration.
  local env_args
  env_args=$(docker inspect "$old" \
    --format='{{range .Config.Env}}-e {{.}} {{end}}' 2>/dev/null || true)

  # Start the canary alongside the old container
  # shellcheck disable=SC2086
  docker run -d \
    --name "$canary" \
    $network_args \
    $env_args \
    "$image"

  if wait_healthy "$canary"; then
    log "  Canary is healthy — cutting over to new version"
    docker stop "$old"  || true
    docker rm   "$old"  || true
    docker rename "$canary" "$old"
    log "=== $svc deploy SUCCEEDED ==="
  else
    log "=== $svc deploy FAILED — canary did not become healthy ==="
    log "    Old container '$old' is still running. Removing canary."
    docker rm -f "$canary" || true
    exit 1
  fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

log "Starting rolling deploy  IMAGE_BASE=${IMAGE_BASE}  SHA=${SHA}"

deploy_service api
deploy_service worker
deploy_service frontend

log "All services updated successfully."
