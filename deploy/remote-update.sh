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
$COMPOSE up -d                          # migrations run on app start (alembic upgrade head)
$COMPOSE ps
docker image prune -f                   # reclaim space from the previous image
echo ">> Deploy complete."
