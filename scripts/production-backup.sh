#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT/deploy"
ENV_FILE="${1:-$DEPLOY_DIR/.env.production}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/docker-compose.production.yml")

[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 1; }
mkdir -p "$DEPLOY_DIR/backups"
chmod 700 "$DEPLOY_DIR/backups"

"${COMPOSE[@]}" --profile maintenance run --rm backup
latest="$(find "$DEPLOY_DIR/backups" -maxdepth 1 -type f -name 'lucyworks-*.dump' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
[[ -n "$latest" && -f "$latest" ]] || { echo "backup file was not produced" >&2; exit 1; }
[[ -f "$latest.sha256" ]] || { echo "checksum file missing for $latest" >&2; exit 1; }
(cd "$DEPLOY_DIR/backups" && sha256sum -c "$(basename "$latest").sha256")
chmod 600 "$latest" "$latest.sha256"
echo "Verified backup: $latest"
