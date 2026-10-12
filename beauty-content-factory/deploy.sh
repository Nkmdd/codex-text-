#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
echo '[1/4] Checking Docker and Compose'
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo 'ERROR: first install needs sudo rights' >&2; exit 1
  fi
  SUDO='' ; [ "$(id -u)" -ne 0 ] && SUDO='sudo'
  $SUDO apt-get update
  $SUDO apt-get install -y docker.io docker-compose-v2
  $SUDO systemctl enable --now docker
fi
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo '[2/4] Created .env. Set WEB_UPLOAD_PASSWORD, DOMAIN, optional Telegram token and ALLOWED_TELEGRAM_USERS before starting.'
  exit 2
fi
if grep -q 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD' .env; then
  echo 'ERROR: configure WEB_UPLOAD_PASSWORD in .env before start' >&2; exit 2
fi
if [ "${PUBLIC:-0}" = '1' ] && grep -q 'DOMAIN=REPLACE_WITH_PUBLIC_DOMAIN' .env; then
  echo 'ERROR: configure DOMAIN in .env first' >&2; exit 2
fi
echo '[2/4] Validating Compose'
COMPOSE_PROFILES=''
if grep -q '^TELEGRAM_BOT_TOKEN=.' .env && grep -q '^ALLOWED_TELEGRAM_USERS=.' .env; then
  COMPOSE_PROFILES='bot'
fi
if [ "${PUBLIC:-0}" = '1' ]; then COMPOSE_PROFILES="${COMPOSE_PROFILES:+${COMPOSE_PROFILES},}public"; fi
export COMPOSE_PROFILES
if [ "$(id -u)" -eq 0 ]; then DC=(docker compose); else DC=(sudo docker compose); fi
"${DC[@]}" config --quiet
echo '[3/4] Build and start'
"${DC[@]}" up -d --build --remove-orphans
echo '[4/4] Health and status'
"${DC[@]}" ps
if [ "${PUBLIC:-0}" = '1' ]; then echo 'Web: https://<DOMAIN> after DNS and HTTPS ready'; fi
echo 'Completed. Data persists in Docker volume; .env is not overwritten.'
