"""HTTP clients for Overseerr, Plex, Radarr, Sonarr, or a Pi stats aggregator."""

import gc

_connection_manager = None


def configure_http(session, pool):
    """Call once from code.py so sockets can be closed without pooling stale data."""
    global _connection_manager
    try:
        from adafruit_connection_manager import get_connection_manager

        _connection_manager = get_connection_manager(pool)
    except ImportError:
        _connection_manager = getattr(session, "_connection_manager", None)


STAT_KEYS = (
    "overseerr_pending",
    "plex_streams",
    "radarr_movies",
    "radarr_missing",
    "radarr_downloads",
    "sonarr_shows",
    "sonarr_episodes",
    "sonarr_missing",
    "sonarr_downloads",
)


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


def _configured(url, key=""):
    if key:
        return url and key and url.strip() and key.strip()
    return url and url.strip()


def _error_once(stats, service):
    if service not in stats["errors"]:
        stats["errors"].append(service)


def _service_headers(api_key):
    return {
        "X-Api-Key": api_key,
        "Connection": "close",
    }


def _destroy_response(response):
    """Close socket for real — do not return it to the pool with unread bytes."""
    if response is None:
        return
    sock = response.socket
    response.socket = None
    if sock is None:
        return
    cm = _connection_manager
    if cm is None:
        sess = getattr(response, "_session", None)
        cm = getattr(sess, "_connection_manager", None) if sess else None
    if cm is not None:
        try:
            cm.close_socket(sock)
        except (RuntimeError, OSError, AttributeError):
            try:
                sock.close()
            except OSError:
                pass
    else:
        try:
            sock.close()
        except OSError:
            pass
    gc.collect()


def _get_json(session, url, headers=None):
    response = session.get(url, headers=headers or {})
    try:
        if response.status_code != 200:
            raise RuntimeError("HTTP %d" % response.status_code)
        return response.json()
    finally:
        _destroy_response(response)


def _apply_payload(stats, payload):
    for key in STAT_KEYS:
        if key in payload and payload[key] is not None:
            stats[key] = payload[key]
    errors = payload.get("errors")
    if isinstance(errors, list):
        stats["errors"] = errors


def fetch_from_aggregator(session, secrets):
    url = secrets.get("aggregator_url", "").rstrip("/")
    headers = {"Connection": "close"}
    key = secrets.get("aggregator_api_key", "")
    if key and key.strip():
        headers["X-Api-Key"] = key.strip()
    stats = empty_stats()
    try:
        payload = _get_json(session, url + "/stats", headers)
        _apply_payload(stats, payload)
        print("Aggregator stats ok")
    except Exception as exc:
        _error_once(stats, "Aggregator")
        print("Aggregator error:", exc)
    return stats


def fetch_overseerr(session, secrets, stats):
    url = secrets.get("overseerr_url", "")
    key = secrets.get("overseerr_api_key", "")
    if not _configured(url, key):
        return
    try:
        data = _get_json(
            session,
            url.rstrip("/") + "/api/v1/request/count",
            {"X-Api-Key": key, "Connection": "close"},
        )
        stats["overseerr_pending"] = int(data.get("pending", 0))
    except Exception as exc:
        _error_once(stats, "Overseerr")
        print("Overseerr error:", exc)


def fetch_plex(session, secrets, stats):
    url = secrets.get("plex_url", "")
    token = secrets.get("plex_token", "")
    if not _configured(url, token):
        return
    try:
        endpoint = url.rstrip("/") + "/status/sessions?X-Plex-Token=" + token
        data = _get_json(
            session,
            endpoint,
            {"Accept": "application/json", "Connection": "close"},
        )
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
        print("Plex error:", exc)


def fetch_radarr(session, secrets, stats):
    url = secrets.get("radarr_url", "")
    key = secrets.get("radarr_api_key", "")
    if not _configured(url, key):
        return
    base = url.rstrip("/")
    headers = _service_headers(key)

    try:
        queue = _get_json(session, base + "/api/v3/queue/status", headers)
        stats["radarr_downloads"] = int(queue.get("totalCount", 0))
    except Exception as exc:
        _error_once(stats, "Radarr")
        print("Radarr queue error:", exc)

    try:
        missing = _get_json(
            session,
            base + "/api/v3/wanted/missing?page=1&pageSize=1",
            headers,
        )
        stats["radarr_missing"] = int(missing.get("totalRecords", 0))
    except Exception as exc:
        _error_once(stats, "Radarr")
        print("Radarr missing error:", exc)


def fetch_sonarr(session, secrets, stats):
    url = secrets.get("sonarr_url", "")
    key = secrets.get("sonarr_api_key", "")
    if not _configured(url, key):
        return
    base = url.rstrip("/")
    headers = _service_headers(key)

    try:
        queue = _get_json(session, base + "/api/v3/queue/status", headers)
        stats["sonarr_downloads"] = int(queue.get("totalCount", 0))
    except Exception as exc:
        _error_once(stats, "Sonarr")
        print("Sonarr queue error:", exc)

    try:
        missing = _get_json(
            session,
            base + "/api/v3/wanted/missing?page=1&pageSize=1",
            headers,
        )
        stats["sonarr_missing"] = int(missing.get("totalRecords", 0))
    except Exception as exc:
        _error_once(stats, "Sonarr")
        print("Sonarr missing error:", exc)


def fetch_all(session, secrets):
    if _configured(secrets.get("aggregator_url", "")):
        return fetch_from_aggregator(session, secrets)

    stats = empty_stats()
    fetch_overseerr(session, secrets, stats)
    fetch_plex(session, secrets, stats)
    fetch_radarr(session, secrets, stats)
    fetch_sonarr(session, secrets, stats)
    return stats
