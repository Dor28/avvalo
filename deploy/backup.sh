#!/usr/bin/env bash
# Avvalo database backup — compressed, optionally encrypted, with rotation.
#
# Runs pg_dump inside the running `db` container, so it needs no DB password on
# the host. Designed to be driven by cron (see docs/DEPLOYMENT.md "Backups").
#
#   ./deploy/backup.sh
#
# Optional env:
#   BACKUP_DIR        where dumps are written            (default /mnt/avvalo-data/backups)
#   KEEP_DAYS         delete local dumps older than N     (default 14)
#   GPG_RECIPIENT     if set, encrypt with this GPG key   (recommended)
#   STORAGE_BOX       rsync target for offsite copy, e.g. u123456@u123456.your-storagebox.de:backups/
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-/mnt/avvalo-data/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/avvalo_${STAMP}.sql.gz"

if [[ -n "${STORAGE_BOX:-}" && -z "${GPG_RECIPIENT:-}" ]]; then
	echo "[backup] refusing offsite copy without GPG_RECIPIENT encryption" >&2
	exit 2
fi

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

echo "[backup] dumping database -> ${OUT}"
# --clean --if-exists makes the dump safe to restore over an existing schema.
docker compose -f "${COMPOSE_FILE}" exec -T db \
	pg_dump -U avvalo -d avvalo --clean --if-exists \
	| gzip -9 > "${OUT}"

if [[ -n "${GPG_RECIPIENT:-}" ]]; then
	echo "[backup] encrypting for ${GPG_RECIPIENT}"
	gpg --yes --batch --encrypt --recipient "${GPG_RECIPIENT}" "${OUT}"
	rm -f "${OUT}"
	OUT="${OUT}.gpg"
fi

chmod 600 "${OUT}"
echo "[backup] wrote $(du -h "${OUT}" | cut -f1) -> ${OUT}"

if [[ -n "${STORAGE_BOX:-}" ]]; then
	echo "[backup] copying offsite -> ${STORAGE_BOX}"
	rsync -az --chmod=600 "${OUT}" "${STORAGE_BOX}"
fi

echo "[backup] pruning local dumps older than ${KEEP_DAYS} days"
find "${BACKUP_DIR}" -name 'avvalo_*.sql.gz*' -mtime "+${KEEP_DAYS}" -delete

echo "[backup] done"
