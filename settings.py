"""Load and save user settings persisted on the CIRCUITPY drive."""

import json

SETTINGS_PATH = "/settings.json"

DEFAULTS = {
    "display_mode": "rotate",
    "rotate_interval_s": 10,
    "refresh_interval_s": 60,
}

VALID_MODES = ("rotate", "single", "priority")


def load():
    """Return settings merged with defaults."""
    settings = DEFAULTS.copy()
    try:
        with open(SETTINGS_PATH, "r") as f:
            stored = json.load(f)
        for key in DEFAULTS:
            if key in stored:
                settings[key] = stored[key]
    except (OSError, ValueError, TypeError):
        pass

    if settings["display_mode"] not in VALID_MODES:
        settings["display_mode"] = DEFAULTS["display_mode"]
    settings["rotate_interval_s"] = max(3, int(settings["rotate_interval_s"]))
    settings["refresh_interval_s"] = max(15, int(settings["refresh_interval_s"]))
    return settings


def save(settings):
    """Persist settings to settings.json."""
    data = {
        "display_mode": settings["display_mode"],
        "rotate_interval_s": int(settings["rotate_interval_s"]),
        "refresh_interval_s": int(settings["refresh_interval_s"]),
    }
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f)
