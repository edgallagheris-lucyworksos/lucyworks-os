#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "Usage: CONFIRM_LUCYWORKS_RESTORE=yes RESTORE_DATABASE_URL=postgresql://... $0 backup.dump" >&2
  exit 1
fi
if [[ "${CONFIRM_LUCYWORKS_RESTORE:-no}" != "yes" ]]; then
  echo "Restore refused. Set CONFIRM_LUCYWORKS_RESTORE=yes after verifying the target is isolated." >&2
  exit 1
fi
if [[ -z "${RESTORE_DATABASE_URL:-}" || "$RESTORE_DATABASE_URL" != postgresql* ]]; then
  echo "RESTORE_DATABASE_URL must point to an isolated PostgreSQL database" >&2
  exit 1
fi
if ! command -v pg_restore >/dev/null 2>&1; then
  echo "pg_restore is not installed" >&2
  exit 1
fi

if [[ -f "$BACKUP_FILE.sha256" ]]; then
  sha256sum -c "$BACKUP_FILE.sha256"
else
  echo "Warning: no SHA-256 manifest found beside backup" >&2
fi

PG_URL="${RESTORE_DATABASE_URL/postgresql+psycopg/postgresql}"
pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error --dbname="$PG_URL" "$BACKUP_FILE"

cat <<EOF
LucyWorks restore completed into the explicitly supplied target.

Required follow-up:
1. Run: cd apps/api && DATABASE_URL="$RESTORE_DATABASE_URL" alembic current
2. Run application smoke tests against the restored database.
3. Record restore duration, row counts, evidence-chain integrity and reviewer.
4. Destroy the rehearsal database when the evidence is retained.
EOF
