#!/bin/sh
set -eu

: "${PROFILE_LOGIN:?PROFILE_LOGIN is required}"
: "${PROFILE_PASSWORD:?PROFILE_PASSWORD is required}"

case "$PROFILE_LOGIN" in
  *:*)
    echo "PROFILE_LOGIN must not contain ':'" >&2
    exit 1
    ;;
esac

if [ "${#PROFILE_PASSWORD}" -lt 16 ]; then
  echo "PROFILE_PASSWORD must be at least 16 characters" >&2
  exit 1
fi

umask 077
printf '%s:{PLAIN}%s\n' "$PROFILE_LOGIN" "$PROFILE_PASSWORD" >/tmp/htpasswd
