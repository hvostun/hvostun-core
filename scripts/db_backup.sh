#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DB_NAME="${POSTGRES_DB:-hvostun_${FASTAPI_ENV:-development}}"
if [[ ! "${DB_NAME}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "invalid database name: ${DB_NAME}" >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-${ROOT}/.data/backup}"
mkdir -p "${BACKUP_DIR}"

STAMP="$(date +%Y-%m-%d_%H%M%S)"
OUT="${BACKUP_DIR}/${DB_NAME}_${STAMP}.sql"
LATEST="${BACKUP_DIR}/${DB_NAME}.sql"

if [[ "${BACKUP_COMPOSE_FILES:-}" == "deploy" ]]; then
  compose=(docker compose -f compose.yml -f compose.deploy.yml)
else
  compose=(docker compose)
fi

if ! "${compose[@]}" exec -T db pg_isready -U postgres -d "${DB_NAME}" >/dev/null; then
  echo "db is not ready. Start with: docker compose up -d db" >&2
  exit 1
fi

dump_args=(-U postgres -d "${DB_NAME}" --no-owner --no-acl)
if [[ "${BACKUP_CLEAN:-1}" != "0" ]]; then
  dump_args+=(--clean --if-exists)
fi

"${compose[@]}" exec -T db pg_dump "${dump_args[@]}" >"${OUT}"

cp "${OUT}" "${LATEST}"

echo "Wrote ${OUT}"
echo "Latest ${LATEST}"
