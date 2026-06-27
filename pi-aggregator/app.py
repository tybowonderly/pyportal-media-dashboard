"""PyPortal stats aggregator — polls media servers and exposes GET /stats."""

import os
import threading
import time

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

REFRESH_INTERVAL_S = int(os.environ.get("REFRESH_INTERVAL_S", "60"))
STARTUP_TIMEOUT_S = int(os.environ.get("STARTUP_TIMEOUT_S", "120"))
AGGREGATOR_API_KEY = os.environ.get("AGGREGATOR_API_KEY", "").strip()

_cache = {
    "stats": None,
    "updated_at": 0.0,
}
_cache_lock = threading.Lock()


def empty_stats():
    return {
        "overseerr_pending": None,
        "plex_streams": None,
        "radarr_movies": None,
        "radarr_missing": None,
        "radarr_downloads": None,
        "sonarr_shows": None,
        "sonarr_episodes": None,
        "sonarr_missing": None,
        "sonarr_downloads": None,
        "errors": [],
    }


def _configured(url, key):
    return bool(url and key and url.strip() and key.strip())


def _error_once(stats, service):
    if service not in stats["errors"]:
        stats["errors"].append(service)


def _get_json(url, headers=None, timeout=120):
    response = requests.get(url, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_overseerr(stats):
    url = os.environ.get("OVERSEERR_URL", "")
    key = os.environ.get("OVERSEERR_API_KEY", "")
    if not _configured(url, key):
        return
    try:
        data = _get_json(
            url.rstrip("/") + "/api/v1/request/count",
            {"X-Api-Key": key},
        )
        stats["overseerr_pending"] = int(data.get("pending", 0))
    except Exception as exc:
        _error_once(stats, "Overseerr")
        app.logger.warning("Overseerr error: %s", exc)


def fetch_plex(stats):
    url = os.environ.get("PLEX_URL", "")
    token = os.environ.get("PLEX_TOKEN", "")
    if not _configured(url, token):
        return
    try:
        endpoint = url.rstrip("/") + "/status/sessions?X-Plex-Token=" + token
        data = _get_json(endpoint, {"Accept": "application/json"})
        container = data.get("MediaContainer", {})
        size = container.get("size")
        if size is not None:
            stats["plex_streams"] = int(size)
        else:
            metadata = container.get("Metadata", [])
            if isinstance(metadata, dict):
                metadata = [metadata]
            stats["plex_streams"] = len(metadata)
    except Exception as exc:
        _error_once(stats, "Plex")
        app.logger.warning("Plex error: %s", exc)


def fetch_radarr(stats):
    url = os.environ.get("RADARR_URL", "")
    key = os.environ.get("RADARR_API_KEY", "")
    if not _configured(url, key):
        return
    base = url.rstrip("/")
    headers = {"X-Api-Key": key}

    try:
        queue = _get_json(base + "/api/v3/queue/status", headers)
        stats["radarr_downloads"] = int(queue.get("totalCount", 0))
    except Exception as exc:
        _error_once(stats, "Radarr")
        app.logger.warning("Radarr queue error: %s", exc)

    try:
        missing = _get_json(
            base + "/api/v3/wanted/missing?page=1&pageSize=1",
            headers,
        )
        stats["radarr_missing"] = int(missing.get("totalRecords", 0))
    except Exception as exc:
        _error_once(stats, "Radarr")
        app.logger.warning("Radarr missing error: %s", exc)

    try:
        movies = _get_json(base + "/api/v3/movie", headers, timeout=180)
        stats["radarr_movies"] = sum(1 for movie in movies if movie.get("hasFile"))
    except Exception as exc:
        _error_once(stats, "Radarr")
        app.logger.warning("Radarr library error: %s", exc)


def fetch_sonarr(stats):
    url = os.environ.get("SONARR_URL", "")
    key = os.environ.get("SONARR_API_KEY", "")
    if not _configured(url, key):
        return
    base = url.rstrip("/")
    headers = {"X-Api-Key": key}

    try:
        queue = _get_json(base + "/api/v3/queue/status", headers)
        stats["sonarr_downloads"] = int(queue.get("totalCount", 0))
    except Exception as exc:
        _error_once(stats, "Sonarr")
        app.logger.warning("Sonarr queue error: %s", exc)

    try:
        missing = _get_json(
            base + "/api/v3/wanted/missing?page=1&pageSize=1",
            headers,
        )
        stats["sonarr_missing"] = int(missing.get("totalRecords", 0))
    except Exception as exc:
        _error_once(stats, "Sonarr")
        app.logger.warning("Sonarr missing error: %s", exc)

    try:
        series = _get_json(base + "/api/v3/series", headers, timeout=180)
        stats["sonarr_shows"] = len(series)
        stats["sonarr_episodes"] = sum(
            item.get("statistics", {}).get("episodeFileCount", 0) for item in series
        )
    except Exception as exc:
        _error_once(stats, "Sonarr")
        app.logger.warning("Sonarr library error: %s", exc)


def fetch_all():
    stats = empty_stats()
    fetch_overseerr(stats)
    fetch_plex(stats)
    fetch_radarr(stats)
    fetch_sonarr(stats)
    return stats


def _refresh_loop():
    while True:
        try:
            stats = fetch_all()
            with _cache_lock:
                _cache["stats"] = stats
                _cache["updated_at"] = time.time()
            app.logger.info(
                "Stats refreshed: radarr_movies=%s sonarr_shows=%s errors=%s",
                stats.get("radarr_movies"),
                stats.get("sonarr_shows"),
                stats.get("errors"),
            )
        except Exception as exc:
            app.logger.exception("Refresh failed: %s", exc)
        time.sleep(REFRESH_INTERVAL_S)


def _wait_for_initial_cache():
    deadline = time.time() + STARTUP_TIMEOUT_S
    while time.time() < deadline:
        with _cache_lock:
            if _cache["stats"] is not None:
                return
        time.sleep(0.5)
    app.logger.warning("Startup timeout: serving empty stats until first refresh")


def _check_auth():
    if not AGGREGATOR_API_KEY:
        return None
    provided = request.headers.get("X-Api-Key", "")
    if provided != AGGREGATOR_API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.get("/health")
def health():
    with _cache_lock:
        ready = _cache["stats"] is not None
        updated_at = _cache["updated_at"]
    return jsonify({"status": "ok", "ready": ready, "updated_at": updated_at})


@app.get("/stats")
def stats():
    auth_error = _check_auth()
    if auth_error:
        return auth_error
    with _cache_lock:
        payload = _cache["stats"]
    if payload is None:
        return jsonify(empty_stats())
    return jsonify(payload)


def main():
    thread = threading.Thread(target=_refresh_loop, daemon=True)
    thread.start()
    _wait_for_initial_cache()
    port = int(os.environ.get("PORT", "8765"))
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
