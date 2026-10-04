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

compose=(docker compose -f compose.yml -f compose.deploy.yml)
config="$("${compose[@]}" config)"

if grep -q -- '--api' <<<"$config"; then
  echo "deploy proxy must not enable Traefik --api" >&2
  exit 1
fi

if grep -E -q 'published: "?(5432|8080|8090)"?' <<<"$config"; then
  echo "deploy must not publish ports 5432, 8080, or 8090" >&2
  exit 1
fi

if [[ "${1:-}" == "up" ]]; then
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
