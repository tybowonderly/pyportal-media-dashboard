# PyPortal Media Server Dashboard

CircuitPython dashboard for the [Adafruit PyPortal](https://www.adafruit.com/product/4116) (320×240) that shows live stats from your homelab media stack:

- **Overseerr** — pending requests
- **Plex** — active streams
- **Radarr** — downloaded movies, missing movies, active downloads
- **Sonarr** — show count, downloaded episodes, missing episodes, active downloads

Three display layouts are available (default: auto-rotate). Tap the gear icon (top-right) to change modes.

## Requirements

- Adafruit PyPortal (original, 320×240)
- CircuitPython 8.x or 9.x
- **Recommended:** Raspberry Pi (or any LAN host) running the stats aggregator in Docker
- Your media servers reachable from the Pi on the same LAN

## Architecture

The PyPortal has limited RAM and a fragile HTTP stack over the ESP32 WiFi coprocessor. Radarr and Sonarr library endpoints are several MB of chunked JSON — too large to fetch reliably on-device.

**Recommended setup:** run the included [`pi-aggregator/`](pi-aggregator/) service on a Raspberry Pi. It polls Overseerr, Plex, Radarr, and Sonarr every 60 seconds and exposes a single **`GET /stats`** endpoint (~300 bytes). The PyPortal makes one quick HTTP request per refresh.

```
PyPortal  ──GET /stats──►  Pi (Docker)  ──►  Overseerr / Plex / Radarr / Sonarr
```

## Setup

### 1. Pi stats aggregator (recommended)

On your Raspberry Pi:

```bash
git clone https://github.com/tybowonderly/pyportal-media-dashboard.git
cd pyportal-media-dashboard/pi-aggregator
cp .env.example .env
# Edit .env with your service URLs and API keys
chmod +x up.sh
./up.sh
```

If `./up.sh` says Compose is missing, install it:

```bash
sudo apt update
sudo apt install docker-compose-plugin   # then: docker compose up -d --build
# or
sudo apt install docker-compose          # then: docker-compose up -d --build
```

See [`pi-aggregator/README.md`](pi-aggregator/README.md) for details.

Verify:

```bash
curl http://localhost:8765/health
curl -H "X-Api-Key: YOUR_KEY" http://localhost:8765/stats
```

You should see all stat fields including `radarr_movies`, `sonarr_shows`, and `sonarr_episodes`.

| Env variable | Description |
|--------------|-------------|
| `OVERSEERR_URL` / `OVERSEERR_API_KEY` | Overseerr base URL and API key |
| `PLEX_URL` / `PLEX_TOKEN` | Plex base URL and token |
| `RADARR_URL` / `RADARR_API_KEY` | Radarr base URL and API key |
| `SONARR_URL` / `SONARR_API_KEY` | Sonarr base URL and API key |
| `AGGREGATOR_API_KEY` | Optional shared secret (PyPortal sends as `X-Api-Key`) |
| `REFRESH_INTERVAL_S` | Background poll interval (default 60) |

Leave a service URL/key blank to skip it.

### 2. Flash CircuitPython

Download the latest `.uf2` for PyPortal from [circuitpython.org/board/pyportal](https://circuitpython.org/board/pyportal/) and drag it onto the `PORTALBOOT` drive.

### 3. Install libraries

With the PyPortal connected (appears as `CIRCUITPY`), install dependencies using [circup](https://github.com/adafruit/circup):

```bash
pip install circup
circup --path /Volumes/CIRCUITPY install \
  adafruit_requests \
  adafruit_esp32spi \
  adafruit_display_text \
  adafruit_connection_manager \
  adafruit_touchscreen
```

Adjust `/Volumes/CIRCUITPY` to match your OS mount point.

### 4. Configure secrets

Copy the example secrets file and fill in WiFi plus your Pi aggregator URL:

```bash
cp secrets.py.example secrets.py
```

Edit `secrets.py` on the CIRCUITPY drive:

| Key | Description |
|-----|-------------|
| `ssid` / `password` | WiFi credentials |
| `aggregator_url` | e.g. `http://192.168.0.100:8765` |
| `aggregator_api_key` | Optional; must match `AGGREGATOR_API_KEY` on Pi |

**Never commit `secrets.py`** — it is listed in `.gitignore`.

Service API keys live in the Pi `.env` file, not on the PyPortal.

### 5. Copy project files

Copy these files to the root of the CIRCUITPY drive:

```
code.py
clients.py
display_ui.py
display_init.py
settings.py
esp32_socketpool.py
```

Reboot the PyPortal (press reset). `code.py` runs automatically on boot.

## Direct mode (fallback)

If `aggregator_url` is omitted from `secrets.py`, the PyPortal calls each service directly. Queue and missing counts work; **library counts** (downloaded movies, show count, episode count) are not available on-device due to memory limits. Use the Pi aggregator for full stats.

## Finding API keys

Configure these in `pi-aggregator/.env` (not on the PyPortal):

### Overseerr

Settings → General → **API Key**

### Plex

https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

### Radarr / Sonarr

Settings → General → **API Key** (same location in both apps)

## Display modes

Open the options screen by tapping the gear icon `[=]` in the top-right corner.

| Mode | Behavior |
|------|----------|
| **Rotate** (default) | Cycles 2 pages every 10s: Overseerr+Plex → Radarr+Sonarr. Tap to skip ahead. |
| **Single** | All stats on one screen. |
| **Priority** | Page 1: Overseerr + Plex (large). Page 2: Radarr + Sonarr. Auto-rotates every 10s. |

Settings are saved to `settings.json` on the device and persist across reboots.

## Troubleshooting

- **ImportError: `adafruit_esp32spi.adafruit_esp32spi_socketpool`** — CircuitPython 8.2.x cannot import nested library submodules. Copy `esp32_socketpool.py` to the CIRCUITPY root. Upgrade to [CircuitPython 9.x+](https://circuitpython.org/board/pyportal/) for a permanent fix.

- **Black screen in REPL** — Press **Ctrl+D** to soft-reboot. Ctrl+C stops the app.

- **WiFi failed** — Check `ssid`/`password` in `secrets.py`. Serial REPL at 115200 baud shows debug output.

- **Aggregator error** — Verify Pi is running: `curl http://PI_IP:8765/stats`. Check PyPortal can reach the Pi IP on port 8765.

- **Stat shows `---`** — Not configured or never fetched successfully.

- **Stat shows `*`** — Last known value; latest fetch failed.

- **Err footer** — Lists services that failed on the most recent refresh.

## Project structure

```
code.py              Main loop: WiFi, fetch, touch, page rotation
clients.py           Aggregator or direct API fetchers
display_ui.py        Screen layouts and touch handling
display_init.py      Display and backlight init
settings.py          Load/save settings.json
esp32_socketpool.py  CP 8.2 socket pool workaround
pi-aggregator/       Docker stats service for Raspberry Pi
secrets.py.example   Template for WiFi and aggregator URL
```

## License

MIT — use and modify freely.
