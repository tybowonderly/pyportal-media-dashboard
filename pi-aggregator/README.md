# Pi stats aggregator

Polls Overseerr, Plex, Radarr, and Sonarr; exposes `GET /stats` for the PyPortal.

## Quick start

```bash
cp .env.example .env
# Edit .env with your URLs and API keys
./up.sh
```

Or manually:

```bash
docker compose up -d --build      # Compose v2 (plugin)
docker-compose up -d --build      # legacy standalone
```

Verify:

```bash
curl http://localhost:8765/health
curl http://localhost:8765/stats
```

## Docker Compose not installed?

Raspberry Pi OS often ships Docker without the `compose` plugin. Install one of these:

**Option A — Compose plugin (recommended):**

```bash
sudo apt update
sudo apt install docker-compose-plugin
docker compose version
```

**Option B — Standalone docker-compose:**

```bash
sudo apt update
sudo apt install docker-compose
docker-compose --version
```

Then run `./up.sh` or the matching command above.

## Without Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
set -a && source .env && set +a
python app.py
```

## Environment

See `.env.example` for all variables. API keys stay in `.env` on the Pi — not on the PyPortal.
