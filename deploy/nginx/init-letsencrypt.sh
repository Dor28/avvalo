#!/bin/sh
# Bootstrap Let's Encrypt TLS certificates for the Avvalo web channel
# (nginx + certbot). Run this ONCE per server when first enabling the web
# channel; renewals afterward are automatic (the `certbot` service renews and
# nginx reloads on its own 6-hour timer).
#
# Prerequisites:
#   * Run from the repo root (next to docker-compose.prod.yml and .env).
#   * DNS for AVVALO_DOMAIN already points at this server (A/AAAA records).
#   * Ports 80 and 443 are open to the internet.
#
# Usage:
#   ./deploy/nginx/init-letsencrypt.sh            # real certificate
#   ./deploy/nginx/init-letsencrypt.sh --staging  # Let's Encrypt staging (for
#                                                  # dry runs; avoids rate limits)
#
# Re-running is safe — it re-issues the certificate from scratch.

set -eu

COMPOSE="docker compose -f docker-compose.prod.yml"

if [ ! -f .env ]; then
    echo "ERROR: run this from the repo root, where docker-compose.prod.yml and .env live." >&2
    exit 1
fi

# Pull the domain + ACME contact email straight out of .env.
AVVALO_DOMAIN=$(grep -E '^AVVALO_DOMAIN=' .env | head -n1 | cut -d= -f2- | tr -d '"'\' | tr -d '[:space:]')
ACME_EMAIL=$(grep -E '^ACME_EMAIL=' .env | head -n1 | cut -d= -f2- | tr -d '"'\' | tr -d '[:space:]')

if [ -z "${AVVALO_DOMAIN:-}" ]; then
    echo "ERROR: AVVALO_DOMAIN is not set in .env." >&2
    exit 1
fi

STAGING=0
[ "${1:-}" = "--staging" ] && STAGING=1

cert_path="/etc/letsencrypt/live/$AVVALO_DOMAIN"
echo "### Bootstrapping TLS for: $AVVALO_DOMAIN (staging=$STAGING)"

# 1. A throwaway self-signed cert so nginx's :443 server can start at all.
echo "### 1/5  Creating a temporary self-signed certificate ..."
$COMPOSE run --rm --entrypoint sh certbot -c "\
  mkdir -p '$cert_path' && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout '$cert_path/privkey.pem' \
    -out '$cert_path/fullchain.pem' \
    -subj '/CN=$AVVALO_DOMAIN' && \
  cp '$cert_path/fullchain.pem' '$cert_path/chain.pem'"

# 2. Start the stack. nginx comes up serving the dummy cert; certbot's webroot
#    (:80 /.well-known/acme-challenge/) is now reachable. Force-recreate nginx
#    so a previously broken container cannot keep running with an empty conf.d.
echo "### 2/5  Starting the stack (nginx will use the temporary cert) ..."
$COMPOSE up -d --force-recreate nginx

# 3. Drop the dummy cert so certbot can write a real one at the same path.
echo "### 3/5  Removing the temporary certificate ..."
$COMPOSE run --rm --entrypoint sh certbot -c "\
  rm -rf '/etc/letsencrypt/live/$AVVALO_DOMAIN' \
         '/etc/letsencrypt/archive/$AVVALO_DOMAIN' \
         '/etc/letsencrypt/renewal/$AVVALO_DOMAIN.conf'"

# 4. Request the real certificate over HTTP-01 using the shared webroot.
echo "### 4/5  Requesting the Let's Encrypt certificate ..."
email_arg="--email $ACME_EMAIL"
[ -z "${ACME_EMAIL:-}" ] && email_arg="--register-unsafely-without-email"
staging_arg=""
[ "$STAGING" -eq 1 ] && staging_arg="--staging"

# shellcheck disable=SC2086
$COMPOSE run --rm --entrypoint certbot certbot certonly \
    --webroot -w /var/www/certbot \
    $staging_arg $email_arg \
    -d "$AVVALO_DOMAIN" \
    --rsa-key-size 4096 \
    --agree-tos --no-eff-email --non-interactive

# 5. Reload nginx so it serves the freshly issued certificate.
echo "### 5/5  Reloading nginx ..."
$COMPOSE exec nginx nginx -s reload || $COMPOSE restart nginx

echo
echo "### Done. Verify:  curl -fsS https://$AVVALO_DOMAIN/healthz"
