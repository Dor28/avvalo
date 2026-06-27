#!/usr/bin/env bash
# Avvalo database restore — the other half of backup.sh.
#
# DESTRUCTIVE: replaces the current contents of the `avvalo` database with the
# dump you pass in. Practice this on a throwaway VM at least once so a real
# recovery is muscle memory, not a first attempt.
#
#   ./deploy/restore.sh /mnt/avvalo-data/backups/avvalo_20260627T030000Z.sql.gz
#   ./deploy/restore.sh backup.sql.gz.gpg            # GPG-encrypted dumps are auto-decrypted
set -euo pipefail

DUMP="${1:?usage: restore.sh <dump.sql.gz[.gpg]>}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"

if [[ ! -f "${DUMP}" ]]; then
	echo "[restore] no such file: ${DUMP}" >&2
	exit 1
fi

echo "[restore] WARNING: this overwrites the live 'avvalo' database."
read -r -p "[restore] type the database name 'avvalo' to confirm: " CONFIRM
[[ "${CONFIRM}" == "avvalo" ]] || { echo "[restore] aborted"; exit 1; }

decompress() {
	case "${DUMP}" in
		*.gpg) gpg --quiet --decrypt "${DUMP}" | gunzip ;;
		*.gz) gunzip -c "${DUMP}" ;;
		*) cat "${DUMP}" ;;
	esac
}

echo "[restore] restoring ${DUMP}"
decompress | docker compose -f "${COMPOSE_FILE}" exec -T db psql -U avvalo -d avvalo

echo "[restore] done — restart the app: docker compose -f docker-compose.prod.yml restart app"
