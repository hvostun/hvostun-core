#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${COMPOSE_FILE:-}" == *override* ]]; then
  echo "COMPOSE_FILE must not include compose.override.yml" >&2
  exit 1
fi
unset COMPOSE_FILE

for arg in "$@"; do
  case "$arg" in
    *override* | *--profile*)
      echo "refusing deploy argument: ${arg}" >&2
      exit 1
      ;;
  esac
done

if [[ ! "${BACKEND_IMAGE:-}" =~ ^ghcr\.io/hvostun/hvostun-backend@sha256:[0-9a-f]{64}$ ]]; then
  echo "BACKEND_IMAGE must be ghcr.io/hvostun/hvostun-backend@sha256:<64 hex>" >&2
  exit 1
fi

compose=(docker compose -f compose.yml -f compose.deploy.yml)
config="$("${compose[@]}" config)"

if grep -q -- '--api' <<<"$config"; then
  echo "deploy proxy must not enable Traefik --api" >&2
  exit 1
fi

if "${compose[@]}" config --format json | python3 -c '
import json, sys
cfg = json.load(sys.stdin)
volumes = json.dumps(cfg["services"]["proxy"].get("volumes") or [])
sys.exit(1 if "docker.sock" in volumes else 0)
'; then
  :
else
  echo "deploy proxy must not mount docker.sock" >&2
  exit 1
fi

if grep -E -q 'published: "?(5432|8080|8090)"?' <<<"$config"; then
  echo "deploy must not publish ports 5432, 8080, or 8090" >&2
  exit 1
fi

if [[ "${1:-}" == "up" ]]; then
  "${compose[@]}" pull prestart backend
  trivy_image="aquasec/trivy:0.66.0@sha256:086971aaf400beebd94e8300fd8ea623774419597169156cec56eec5b00dfb1e"
  if command -v trivy >/dev/null 2>&1; then
    trivy image --severity HIGH,CRITICAL --exit-code 1 "${BACKEND_IMAGE}"
  else
    docker run --rm \
      -v /var/run/docker.sock:/var/run/docker.sock \
      "$trivy_image" image --severity HIGH,CRITICAL --exit-code 1 "${BACKEND_IMAGE}"
  fi
  "${compose[@]}" up -d db
  ready=0
  for _ in $(seq 1 30); do
    if "${compose[@]}" exec -T db pg_isready -U postgres -d hvostun_production >/dev/null; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "${ready}" -ne 1 ]]; then
    echo "db is not ready for pre-migration backup" >&2
    exit 1
  fi
  POSTGRES_DB=hvostun_production BACKUP_CLEAN=0 BACKUP_COMPOSE_FILES=deploy \
    bash scripts/db_backup.sh
fi

"${compose[@]}" "$@"

detach=0
for arg in "$@"; do
  if [[ "${arg}" == "-d" || "${arg}" == "--detach" ]]; then
    detach=1
  fi
done

if [[ "${1:-}" == "up" && "${detach}" -eq 1 ]]; then
  deadline=$((SECONDS + 120))
  healthy=0
  while (( SECONDS < deadline )); do
    if "${compose[@]}" ps --format json | python3 -c '
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    sys.exit(1)
if raw.startswith("["):
    items = json.loads(raw)
else:
    items = [json.loads(line) for line in raw.splitlines() if line.strip()]
for item in items:
    if item.get("Service") != "backend":
        continue
    health = item.get("Health") or ""
    status = item.get("Status") or ""
    if health == "healthy" or "(healthy)" in status:
        sys.exit(0)
sys.exit(1)
'; then
      healthy=1
      break
    fi
    sleep 2
  done
  if [[ "${healthy}" -ne 1 ]]; then
    echo "backend did not become healthy within 120s" >&2
    "${compose[@]}" logs --no-color backend prestart >&2 || true
    exit 1
  fi
fi
