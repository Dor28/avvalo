#!/usr/bin/env bash
# Refresh the running production stack to a specific image tag pulled from GHCR.
#
#   deploy/remote-update.sh <image-tag>        e.g. deploy/remote-update.sh sha-abcdef123456
#
# Invoked by the GitHub Actions deploy job (.github/workflows/deploy.yml) after it
# rsyncs the repo to the server. Safe to run by hand for a manual deploy/rollback.
set -euo pipefail

TAG="${1:?usage: remote-update.sh <image-tag>}"
cd "$(dirname "$0")/.."                 # repo root (~/avvalo)

COMPOSE="docker compose -f docker-compose.prod.yml"

# Pin the image tag in .env so compose — and any later manual command — runs the
# exact same image. (.env already holds every other secret; we only touch this line.)
if grep -q '^IMAGE_TAG=' .env 2>/dev/null; then
  sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=${TAG}|" .env
else
  echo "IMAGE_TAG=${TAG}" >> .env
fi

echo ">> Deploying image tag: ${TAG}"
$COMPOSE pull app                       # requires a one-time `docker login ghcr.io` on this host

# Docker can briefly report "removal ... is already in progress" while replacing
# the previous app container. Retry the idempotent Compose update a few times so
# that transient daemon state does not leave a tested image undeployed.
for attempt in 1 2 3; do
  # `--wait` keeps CI pending until migrations finish and the app healthcheck
  # passes instead of reporting success for a container that is crash-looping.
  if $COMPOSE up -d --wait --wait-timeout 180; then
    break
  fi
  if [ "$attempt" -eq 3 ]; then
    echo ">> Compose update failed after ${attempt} attempts." >&2
    exit 1
  fi
  echo ">> Compose update attempt ${attempt} failed; retrying in 5 seconds..." >&2
  sleep 5
done

$COMPOSE ps
docker image prune -f                   # reclaim space from the previous image
echo ">> Deploy complete."
