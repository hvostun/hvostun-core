#!/usr/bin/env bash
# Idempotent cluster roles for the admin contour.
# hvostun_migrator owns schema objects and runs Alembic.
# hvostun_app is the runtime role: DML only.
set -euo pipefail

: "${PGHOST:=db}"
: "${PGUSER:=postgres}"
: "${PGPASSWORD:?POSTGRES password is required}"
: "${POSTGRES_DB:?}"
: "${POSTGRES_APP_PASSWORD:?}"
: "${POSTGRES_MIGRATOR_PASSWORD:?}"

export PGHOST PGUSER PGPASSWORD

psql -v ON_ERROR_STOP=1 -d postgres \
  -v app_password="$POSTGRES_APP_PASSWORD" \
  -v migrator_password="$POSTGRES_MIGRATOR_PASSWORD" \
  -v dbname="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE hvostun_migrator LOGIN PASSWORD %L', :'migrator_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hvostun_migrator')\gexec
SELECT format('CREATE ROLE hvostun_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hvostun_app')\gexec
ALTER ROLE hvostun_migrator WITH LOGIN PASSWORD :'migrator_password';
ALTER ROLE hvostun_app WITH LOGIN PASSWORD :'app_password';
SELECT format('GRANT CONNECT ON DATABASE %I TO hvostun_migrator, hvostun_app', :'dbname')\gexec
SQL

psql -v ON_ERROR_STOP=1 -d "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
ALTER SCHEMA public OWNER TO hvostun_migrator;
GRANT USAGE ON SCHEMA public TO hvostun_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hvostun_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hvostun_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO hvostun_app;

ALTER DEFAULT PRIVILEGES FOR ROLE hvostun_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hvostun_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hvostun_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO hvostun_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hvostun_migrator IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO hvostun_app;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hvostun_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO hvostun_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO hvostun_app;

DO $$
DECLARE
  obj record;
BEGIN
  FOR obj IN
    SELECT c.relkind, n.nspname AS schema_name, c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
      AND NOT EXISTS (
        SELECT 1 FROM pg_depend d
        WHERE d.objid = c.oid AND d.deptype = 'e'
      )
  LOOP
    IF obj.relkind = 'S' THEN
      EXECUTE format(
        'ALTER SEQUENCE %I.%I OWNER TO hvostun_migrator',
        obj.schema_name, obj.relname
      );
    ELSIF obj.relkind IN ('v', 'm') THEN
      EXECUTE format(
        'ALTER VIEW %I.%I OWNER TO hvostun_migrator',
        obj.schema_name, obj.relname
      );
    ELSE
      EXECUTE format(
        'ALTER TABLE %I.%I OWNER TO hvostun_migrator',
        obj.schema_name, obj.relname
      );
    END IF;
  END LOOP;

  FOR obj IN
    SELECT n.nspname AS schema_name, p.proname, pg_get_function_identity_arguments(p.oid) AS args
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND NOT EXISTS (
        SELECT 1 FROM pg_depend d
        WHERE d.objid = p.oid AND d.deptype = 'e'
      )
  LOOP
    EXECUTE format(
      'ALTER FUNCTION %I.%I(%s) OWNER TO hvostun_migrator',
      obj.schema_name, obj.proname, obj.args
    );
  END LOOP;
END
$$;
SQL
