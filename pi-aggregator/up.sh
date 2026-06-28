#!/bin/sh
# Start the stats aggregator (works with Compose v2 plugin or legacy docker-compose).
set -e
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
  exec docker compose up -d --build "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose up -d --build "$@"
fi

echo "Docker Compose not found." >&2
echo "" >&2
echo "Install on Raspberry Pi OS:" >&2
echo "  sudo apt update" >&2
echo "  sudo apt install docker-compose-plugin" >&2
echo "" >&2
echo "Or the standalone tool:" >&2
echo "  sudo apt install docker-compose" >&2
exit 1
