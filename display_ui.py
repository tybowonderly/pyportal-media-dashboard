"""Display layouts and touch handling for the media dashboard."""

import board
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_touchscreen

import display_init
from clients import STAT_KEYS

SCREEN_W = 320
SCREEN_H = 240

BG = 0x101820
HEADER = 0x8899AA
WHITE = 0xFFFFFF
MUTED = 0x556677
BTN = 0x223344
BTN_SEL = 0x336699
OVERSEERR = 0x5599FF
PLEX = 0xE5A00D
RADARR = 0xFFCC00
SONARR = 0x35C5F4
ERROR = 0xFF6644

GEAR_RECT = (288, 0, 320, 28)
SAVE_RECT = (60, 195, 260, 230)
MODE_RECTS = {
    "rotate": (20, 70, 300, 105),
    "single": (20, 115, 300, 150),
    "priority": (20, 160, 300, 195),
}


class DashboardUI:
    def __init__(self, display):
        self.display = display
        self.touchscreen = adafruit_touchscreen.Touchscreen(
            board.TOUCH_XR,
            board.TOUCH_XL,
            board.TOUCH_YU,
            board.TOUCH_YD,
        )
        self.root = displayio.Group()
        bg_bitmap = displayio.Bitmap(SCREEN_W, SCREEN_H, 1)
        bg_palette = displayio.Palette(1)
        bg_palette[0] = BG
        self.root.append(
            displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)
        )
        self.labels = []
        self._pending_mode = "rotate"
        self.show_options = False
        self._last_signature = None
        display_init.show_group(display, self.root)

    def read_touch(self):
        point = self.touchscreen.touch_point
        if point is None:
            return None
        return point

    @staticmethod
    def _in_rect(x, y, rect):
        x0, y0, x1, y1 = rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def handle_touch(self, point, settings, page, page_count):
        if point is None:
            return None, page

        x, y, _z = point

        if self._in_rect(x, y, GEAR_RECT):
            self.show_options = True
            self._pending_mode = settings["display_mode"]
            return "options_open", page

        if self.show_options:
            for mode, rect in MODE_RECTS.items():
                if self._in_rect(x, y, rect):
                    self._pending_mode = mode
                    return "mode_select", page
            if self._in_rect(x, y, SAVE_RECT):
                settings["display_mode"] = self._pending_mode
                self.show_options = False
                page = 0
                return "save", page
            return None, page

        mode = settings["display_mode"]
        if mode in ("rotate", "priority") and page_count > 1:
            page = (page + 1) % page_count
            return "next_page", page
        return None, page

    def page_count(self, settings):
        mode = settings["display_mode"]
        if mode in ("rotate", "priority"):
            return 2
        return 1

    def _clear_labels(self):
        for lbl in self.labels:
            self.root.remove(lbl)
        self.labels = []

    def _add(self, text, x, y, color=WHITE, scale=2):
        lbl = label.Label(terminalio.FONT, text=text, color=color, scale=scale, x=x, y=y)
        self.labels.append(lbl)
        self.root.append(lbl)
        return lbl

    @staticmethod
    def _fmt(value, service, errors):
        if value is None:
            return "---"
        text = str(value)
        if service in errors:
            text += "*"
        return text

    def _render_service_column(
        self,
        rows,
        stats,
        errors,
        service,
        color,
        x_label,
        x_value,
        y_start,
        row_h,
        label_scale=1,
        value_scale=2,
    ):
        y = y_start
        for row_label, key in rows:
            self._add(row_label, x_label, y, MUTED, scale=label_scale)
            self._add(
                self._fmt(stats[key], service, errors),
                x_value,
                y,
                color,
                scale=value_scale,
            )
            y += row_h

    def render(
        self,
        stats,
        settings,
        page,
        wifi_ok,
        refresh_label,
        last_stats=None,
    ):
        errors = stats.get("errors", [])
        display_stats = stats
        if last_stats:
            display_stats = {
                key: stats.get(key) if stats.get(key) is not None else last_stats.get(key)
                for key in STAT_KEYS
            }

        signature = (
            page,
            settings["display_mode"],
            self.show_options,
            self._pending_mode,
            wifi_ok,
            refresh_label,
            tuple(errors),
        ) + tuple(display_stats[key] for key in STAT_KEYS)
        if signature == self._last_signature:
            return
        self._last_signature = signature

        self._clear_labels()
        wifi_text = "WiFi OK" if wifi_ok else "No WiFi"
        self._add(wifi_text, 4, 12, HEADER if wifi_ok else ERROR, scale=1)
        self._add(refresh_label, 4, 24, MUTED, scale=1)
        self._add("[=]", 292, 12, MUTED, scale=1)

        if self.show_options:
            self._render_options(settings)
            return

        mode = settings["display_mode"]
        if mode == "single":
            self._render_single(display_stats, errors)
        elif mode == "priority":
            if page == 0:
                self._render_priority_primary(display_stats, errors)
            else:
                self._render_priority_secondary(display_stats, errors)
        else:
            if page == 0:
                self._render_rotate_page1(display_stats, errors)
            else:
                self._render_arr_combined(display_stats, errors)

        if errors:
            self._add("Err: " + ",".join(errors), 4, 234, ERROR, scale=1)

    def _render_options(self, settings):
        self._add("Display Mode", 70, 40, WHITE, scale=2)
        for mode, rect in MODE_RECTS.items():
            x0, y0, x1, y1 = rect
            selected = mode == self._pending_mode
            title = mode.capitalize()
            if mode == settings["display_mode"]:
                title += " (current)"
            self._add(title, x0 + 10, y0 + 22, BTN_SEL if selected else BTN, scale=1)
        self._add("Save & Back", 95, 218, WHITE, scale=2)

    def _render_single(self, stats, errors):
        self._add("Overseerr", 8, 48, OVERSEERR, scale=1)
        self._add(self._fmt(stats["overseerr_pending"], "Overseerr", errors), 200, 48, WHITE, scale=1)
        self._add("Plex", 8, 68, PLEX, scale=1)
        self._add(self._fmt(stats["plex_streams"], "Plex", errors), 200, 68, WHITE, scale=1)
        self._add("Radarr", 40, 92, RADARR, scale=1)
        self._add("Sonarr", 185, 92, SONARR, scale=1)
        self._render_service_column(
            (
                ("Movies", "radarr_movies"),
                ("Missing", "radarr_missing"),
                ("DL", "radarr_downloads"),
            ),
            stats,
            errors,
            "Radarr",
            RADARR,
            x_label=8,
            x_value=95,
            y_start=112,
            row_h=22,
            value_scale=1,
        )
        self._render_service_column(
            (
                ("Shows", "sonarr_shows"),
                ("Episodes", "sonarr_episodes"),
                ("Missing", "sonarr_missing"),
                ("DL", "sonarr_downloads"),
            ),
            stats,
            errors,
            "Sonarr",
            SONARR,
            x_label=168,
            x_value=255,
            y_start=112,
            row_h=22,
            value_scale=1,
        )

    def _render_rotate_page1(self, stats, errors):
        self._add("Overseerr", 20, 80, OVERSEERR, scale=2)
        self._add(
            self._fmt(stats["overseerr_pending"], "Overseerr", errors),
            20,
            120,
            WHITE,
            scale=3,
        )
        self._add("pending requests", 20, 155, MUTED, scale=1)
        self._add("Plex", 180, 80, PLEX, scale=2)
        self._add(
            self._fmt(stats["plex_streams"], "Plex", errors),
            180,
            120,
            WHITE,
            scale=3,
        )
        self._add("active streams", 180, 155, MUTED, scale=1)

    def _render_arr_combined(self, stats, errors):
        self._add("Radarr", 54, 44, RADARR, scale=2)
        self._add("Sonarr", 190, 44, SONARR, scale=2)
        self._add("|", 158, 44, MUTED, scale=1)

        row_h = 36
        y_start = 88
        self._render_service_column(
            (
                ("Movies", "radarr_movies"),
                ("Missing", "radarr_missing"),
                ("DL", "radarr_downloads"),
            ),
            stats,
            errors,
            "Radarr",
            RADARR,
            x_label=12,
            x_value=108,
            y_start=y_start + row_h // 2,
            row_h=row_h,
        )
        self._render_service_column(
            (
                ("Shows", "sonarr_shows"),
                ("Episodes", "sonarr_episodes"),
                ("Missing", "sonarr_missing"),
                ("DL", "sonarr_downloads"),
            ),
            stats,
            errors,
            "Sonarr",
            SONARR,
            x_label=172,
            x_value=268,
            y_start=y_start,
            row_h=row_h,
        )

    def _render_priority_primary(self, stats, errors):
        self._add("Overseerr Pending", 20, 70, OVERSEERR, scale=2)
        self._add(
            self._fmt(stats["overseerr_pending"], "Overseerr", errors),
            20,
            115,
            WHITE,
            scale=4,
        )
        self._add("Plex Active Streams", 20, 165, PLEX, scale=2)
        self._add(
            self._fmt(stats["plex_streams"], "Plex", errors),
            20,
            210,
            WHITE,
            scale=3,
        )

    def _render_priority_secondary(self, stats, errors):
        self._render_arr_combined(stats, errors)

    def render_loading(self, message):
        self._last_signature = None
        self._clear_labels()
        self._add("Media Dashboard", 40, 70, WHITE, scale=2)
        self._add(message, 20, 120, HEADER, scale=1)

    def render_error(self, message):
        self._last_signature = None
        self._clear_labels()
        self._add("Media Dashboard", 40, 80, WHITE, scale=2)
        self._add(message, 20, 130, ERROR, scale=1)
