# Pi stats aggregator

Polls Overseerr, Plex, Radarr, and Sonarr; exposes `GET /stats` for the PyPortal.

## Quick start

```bash
cp .env.example .env
# Edit .env with your URLs and API keys
./up.sh
```

Or manually (use `sudo` if you get permission denied on the Docker socket):

```bash
sudo docker compose up -d --build      # snap or Compose v2 plugin
sudo docker-compose up -d --build      # legacy standalone
```

Verify:

```bash
curl http://localhost:8765/health
curl http://localhost:8765/stats
```

## Permission denied on `/var/run/docker.sock`?

Your user is not allowed to talk to Docker yet. Either use `sudo`:

```bash
sudo docker compose up -d --build
```

Or add yourself to the `docker` group (log out and back in afterward):

```bash
sudo usermod -aG docker "$USER"
# snap installs may also need:
sudo snap connect docker:docker-daemon
```

## Docker Compose not installed?

**Snap (includes Compose v2):**

```bash
sudo snap install docker
sudo docker compose up -d --build
```

**Debian/Raspberry Pi OS apt packages:**

```bash
sudo apt update
sudo apt install docker-compose-plugin
sudo docker compose up -d --build
```

Legacy standalone:

```bash
sudo apt install docker-compose
sudo docker-compose up -d --build
```

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
