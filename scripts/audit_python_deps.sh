#!/usr/bin/env bash
# Audit the frozen app lockfile. PYSEC-2026-4146 (PyJWT options-dict mutation)
# last affects 2.13.0; app code never passes an options dict to jwt.decode.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv export --frozen --no-hashes --package app --no-dev \
  | uvx pip-audit -r /dev/stdin --no-deps --disable-pip
