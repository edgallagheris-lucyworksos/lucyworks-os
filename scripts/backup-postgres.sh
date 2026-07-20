#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi
if [[ "$DATABASE_URL" != postgresql* ]]; then
  echo "Backup command requires PostgreSQL; refusing non-PostgreSQL URL" >&2
  exit 1
fi
if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump is not installed" >&2
  exit 1
fi

OUTPUT_DIR="${BACKUP_OUTPUT_DIR:-./backups}"
mkdir -p "$OUTPUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DATABASE_NAME="${BACKUP_DATABASE_LABEL:-lucyworks}"
OUTPUT="$OUTPUT_DIR/${DATABASE_NAME}-${STAMP}.dump"
MANIFEST="$OUTPUT.sha256"
PG_URL="${DATABASE_URL/postgresql+psycopg/postgresql}"

umask 077
pg_dump --format=custom --compress=9 --no-owner --no-privileges --file="$OUTPUT" "$PG_URL"
sha256sum "$OUTPUT" > "$MANIFEST"

cat <<EOF
LucyWorks PostgreSQL backup completed.
Backup:  $OUTPUT
Manifest: $MANIFEST
Verify:  sha256sum -c "$MANIFEST"

This command creates a backup; it does not prove restoreability. Run a scheduled
restore rehearsal into an isolated database and record the evidence reference.
EOF
