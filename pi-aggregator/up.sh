#!/bin/sh
# Start the stats aggregator (Compose v2 plugin, legacy docker-compose, or sudo).
set -e
cd "$(dirname "$0")"

run_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@" || sudo docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@" || sudo docker-compose "$@"
    return
  fi
  echo "Docker Compose not found." >&2
  echo "  sudo apt install docker-compose-plugin" >&2
  echo "  sudo snap install docker          # includes compose" >&2
  exit 1
}

run_compose up -d --build "$@"
