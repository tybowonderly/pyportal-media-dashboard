"""PyPortal media server dashboard — main entry point."""

import gc
import time

print("code.py starting")

import board
import busio
from digitalio import DigitalInOut

# ESP32 WiFi coprocessor needs SPI — claim it before displayio import
spi = board.SPI()
print("spi ok")

import adafruit_esp32spi.adafruit_esp32spi as esp32spi
import esp32_socketpool
from adafruit_connection_manager import create_fake_ssl_context
import adafruit_requests

import clients
import display_init
import display_ui
import settings

display = display_init.init_display()
print("display ok", display)

esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
esp = esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
print("esp32 ok")

pool = esp32_socketpool.SocketPool(esp)
ssl_context = create_fake_ssl_context(pool, esp)
http = adafruit_requests.Session(pool, ssl_context)
clients.configure_http(http, pool)
print("imports ok")

ui = display_ui.DashboardUI(display)
ui.render_loading("Starting...")
gc.collect()
print("ui ok")

try:
    from secrets import secrets
except ImportError:
    ui.render_error("Copy secrets.py.example to secrets.py")
    while True:
        time.sleep(60)

cfg = settings.load()
stats = clients.empty_stats()
last_good = clients.empty_stats()
page = 0
last_fetch = 0
last_rotate = time.monotonic()
last_touch = 0
wifi_ok = False
refresh_label = "Waiting..."
needs_render = True


def format_ip(esp_device):
    try:
        return esp_device.ipv4_address
    except AttributeError:
        return esp_device.pretty_ip(esp_device.ip_address)


def connect_wifi():
    global wifi_ok, needs_render
    ui.render_loading("Connecting WiFi...")
    needs_render = True
    for attempt in range(5):
        try:
            print("Connecting WiFi:", secrets["ssid"], "attempt", attempt + 1)
            esp.connect(secrets)
            wifi_ok = True
            print("Connected:", format_ip(esp))
            needs_render = True
            return True
        except OSError as exc:
            print("WiFi error:", exc)
            wifi_ok = False
            ui.render_loading("WiFi retry %d/5..." % (attempt + 1))
            time.sleep(2 ** attempt)
    return False


def ensure_wifi():
    global wifi_ok
    try:
        if esp.status == esp32spi.WL_CONNECTED:
            wifi_ok = True
            return True
    except OSError:
        pass
    wifi_ok = False
    return connect_wifi()


if not connect_wifi():
    ui.render_error("WiFi failed - check secrets.py")
    while True:
        time.sleep(30)
        if connect_wifi():
            break

print("entering main loop")

while True:
    try:
        now = time.monotonic()
        dirty = needs_render

        touch = ui.read_touch()
        if touch and (now - last_touch) > 0.35:
            last_touch = now
            action, page = ui.handle_touch(touch, cfg, page, ui.page_count(cfg))
            if action == "save":
                settings.save(cfg)
                page = 0
                last_rotate = now
                dirty = True
            elif action in ("next_page", "options_open", "mode_select"):
                last_rotate = now
                dirty = True

        if ensure_wifi() and (now - last_fetch) >= cfg["refresh_interval_s"]:
            print("Fetching stats...")
            stats = clients.fetch_all(http, secrets)
            for key in last_good:
                if key == "errors":
                    continue
                if stats[key] is not None:
                    last_good[key] = stats[key]
            last_fetch = now
            refresh_label = "Updated"
            dirty = True
            gc.collect()

        if (
            cfg["display_mode"] in ("rotate", "priority")
            and not ui.show_options
            and (now - last_rotate) >= cfg["rotate_interval_s"]
        ):
            page_count = ui.page_count(cfg)
            page = (page + 1) % page_count
            last_rotate = now
            dirty = True

        if dirty:
            ui.render(stats, cfg, page, wifi_ok, refresh_label, last_stats=last_good)
            needs_render = False

        time.sleep(0.25)
    except Exception as exc:
        print("Error:", exc)
        ui.render_error(str(exc)[:40])
        time.sleep(5)
        needs_render = True
