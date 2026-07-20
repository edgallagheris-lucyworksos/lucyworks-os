#!/bin/sh
set -eu

if [ "${AUTO_CREATE_SCHEMA:-false}" = "true" ]; then
  echo "AUTO_CREATE_SCHEMA=true is not permitted in the production container" >&2
  exit 1
fi

if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "Applying reviewed Alembic migrations"
  alembic upgrade head
fi

exec "$@"
