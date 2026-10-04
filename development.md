# FastAPI Project - Development

## Local Development

For local development, run PostgreSQL and Mailpit with Docker Compose, and run the FastAPI development server locally. The HTML admin is served by FastAPI.

Copy `.env.example` to `.env` before `docker compose up`.

Start the supporting services:

```bash
docker compose up -d db mailpit
```

Then, from the `backend` directory, install the dependencies and prepare the database:

```bash
uv sync
uv run bash scripts/prestart.sh
```

Start the FastAPI development server:

```bash
uv run fastapi dev
```

Now you can open these URLs:

HTML admin: <http://localhost:8000>

Health: <http://localhost:8000/health>

Mailpit: <http://localhost:8025>

The catalog `frontend/` is an inactive React template for a future user UI. It
is not served, built, deployed, or allowed through CORS by the backend. Its
generated client is not kept in sync with the current API.

## Full Stack with Docker Compose

To run the backend (HTML admin) in Docker Compose:

```bash
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

Now you can open these URLs:

Application, with the HTML admin served by FastAPI: <http://localhost:8000>

db-ui - database web administration: <http://localhost:8080>

Traefik UI, to see how the routes are being handled by the proxy: <http://localhost:8090>

Mailpit: <http://localhost:8025>

Stop a locally running FastAPI server before starting the Compose backend because both use port `8000`.

**Note**: The first time you start the stack, it might take a minute for all the services to be ready. To monitor it, use `docker compose logs`, or `docker compose logs backend` for the backend service.

## Mailpit

[Mailpit](https://mailpit.axllent.org) captures emails sent during local development instead of delivering them. The local backend connects to it at `localhost:1025`, and the Compose backend connects to the `mailpit` service. Captured emails are available at <http://localhost:8025>.

## Docker Compose Files and Environment Variables

The main `compose.yml` file contains the configuration shared by the whole stack. Docker Compose loads it automatically.

The `compose.override.yml` file adds local development settings, such as mounting the source code as a volume. Docker Compose also loads it automatically and applies it on top of `compose.yml`.

The `compose.deploy.yml` file contains the deployment-specific settings, including HTTPS and automatic certificate handling. It is explicitly combined with `compose.yml` when deploying the application.

Set a public `DOMAIN`, `LETSENCRYPT_EMAIL`, and production secrets, then deploy with:

```bash
bash scripts/deploy.sh up -d --build
```

The deployment override forces `FASTAPI_ENV=production`, uses the
`hvostun_production` database, runs Alembic and initial superuser setup in a
one-shot `prestart` service, and does not start or expose `db-ui`.

The backend reads local settings from the `.env` file (copy from `.env.example`). Docker Compose also uses it for variable interpolation and passes the settings each container needs.

After changing variables, make sure you restart the stack:

```bash
docker compose watch
```

## The `.env` File

`.env` is not committed. Start from `.env.example`: local development defaults, passwords, and other configuration. Its hostnames use `localhost` for processes running on your machine. Docker Compose overrides hostnames such as the database and SMTP server with their Compose service names.

The Postgres database name is `hvostun_{FASTAPI_ENV}` (local default: `hvostun_development`). Settings rewrites `DATABASE_URL` to that name, so `FASTAPI_ENV=test` always uses `hvostun_test`. Backend tests set `FASTAPI_ENV=test` and create/migrate `hvostun_test` on first run (`uv run pytest` from `backend/`, or `uv run bash scripts/test.sh`).

Dump the local development database (catalog and PII stay out of git):

```bash
bash scripts/db_backup.sh
```

The script writes `.data/backup/hvostun_development_YYYY-MM-DD_HHMMSS.sql` and copies it to `.data/backup/hvostun_development.sql`. The database name comes from `POSTGRES_DB`, or `hvostun_${FASTAPI_ENV:-development}` when that variable is unset. This local dump includes `--clean`. Restore with:

```bash
docker compose exec -T db psql -U postgres -d hvostun_development < .data/backup/hvostun_development.sql
```

`bash scripts/deploy.sh up` dumps `hvostun_production` without `--clean` before `prestart` runs `alembic upgrade`. `pull` and `config` do not dump.

Do not store deployment secrets in `.env`. Keep production secrets in your host/CI secret store.

## Pre-commit Hooks and Code Linting

The project uses [prek](https://prek.j178.dev/), a modern alternative to [pre-commit](https://pre-commit.com/), for code linting and formatting.

You can find a file `.pre-commit-config.yaml` with configurations at the root of the project.

### Install `prek` to Run Automatically

`prek` is already part of the dependencies of the project.

From the project root, install the Git hook so that `prek` runs automatically before each commit:

```bash
uv run prek install -f
```

The `-f` flag forces the installation, in case there was already a `pre-commit` hook previously installed.

Now whenever you try to commit, for example with:

```bash
git commit
```

`prek` will check and format the code you are about to commit. If it modifies any files, add those files to Git again before committing.

### Run `prek` Manually

You can also run `prek` manually on all files from the project root:

```bash
uv run prek run --all-files
```
