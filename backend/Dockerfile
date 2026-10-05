FROM python:3.14.8-slim@sha256:c3e521df8b2b498a7a682e7e18676771cb80c6b75b8699af886b2d554ce40151

ENV PYTHONUNBUFFERED=1

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b /uv /uvx /bin/

# Base-image pip vendors msgpack 1.1.2, urllib3 2.7.0 and setuptools 70.3.0.
# Runtime uses the uv venv. Drop pip and the ensurepip wheel so Trivy does not flag them.
RUN python - <<'PY'
import pathlib
import shutil
import sysconfig

purelib = pathlib.Path(sysconfig.get_path("purelib"))
scripts = pathlib.Path(sysconfig.get_path("scripts"))
bundled = pathlib.Path(sysconfig.get_path("stdlib")) / "ensurepip" / "_bundled"
for path in purelib.glob("pip*"):
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
for path in scripts.glob("pip*"):
    if path.is_symlink() or path.is_file():
        path.unlink()
if bundled.exists():
    shutil.rmtree(bundled)
PY

# CVE-2026-103111 is fixed in libpcre2-8-0 10.46-1~deb13u3.
# libpq5 uses that library. The image does not install psycopg-binary:
# its wheel vendors libpcre2 10.32 from EL8.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends libpcre2-8-0 \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-package psycopg-binary --no-install-workspace --package app

COPY ./backend/scripts /app/backend/scripts

COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/

COPY ./backend/app /app/backend/app

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-package psycopg-binary --package app

RUN groupadd --system --gid 999 hvostun \
 && useradd --system --gid 999 --uid 999 --no-create-home hvostun \
 && chown -R hvostun:hvostun /app
USER hvostun

WORKDIR /app/backend/

CMD ["fastapi", "run", "--workers", "4"]
