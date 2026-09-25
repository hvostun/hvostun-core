#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${ROOT}/.data/backup"
mkdir -p "${BACKUP_DIR}"

STAMP="$(date +%Y-%m-%d_%H%M%S)"
OUT="${BACKUP_DIR}/hvostun_development_${STAMP}.sql"
LATEST="${BACKUP_DIR}/hvostun_development.sql"

if ! docker compose exec -T db pg_isready -U postgres -d hvostun_development >/dev/null; then
  echo "db is not ready. Start with: docker compose up -d db" >&2
  exit 1
fi

docker compose exec -T db pg_dump \
  -U postgres \
  -d hvostun_development \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  >"${OUT}"

cp "${OUT}" "${LATEST}"

echo "Wrote ${OUT}"
echo "Latest ${LATEST}"
