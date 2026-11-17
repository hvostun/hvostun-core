#! /usr/bin/env sh

# Exit in case of error
set -e
set -x

docker compose build
docker compose down -v --remove-orphans # Remove possibly previous broken stacks left hanging after an error
docker compose up -d
# Pytest creates hvostun_test and migrates it. The runtime role cannot do that.
pg_password="$(docker compose exec -T db printenv POSTGRES_PASSWORD | tr -d '\r')"
docker compose exec -T \
  -e "DATABASE_URL=postgresql://postgres:${pg_password}@db:5432/hvostun_test" \
  backend bash scripts/tests-start.sh "$@"
docker compose down -v --remove-orphans
