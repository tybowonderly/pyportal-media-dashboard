#!/bin/sh
# Fix adafruit_esp32spi_socketpool import on CircuitPython 8.2.x
# Run after circup install if you see:
#   ImportError: no module named 'adafruit_esp32spi.adafruit_esp32spi_socketpool'

TARGET="${1:-/Volumes/CIRCUITPY}"
FILE="$TARGET/lib/adafruit_esp32spi/adafruit_esp32spi_socketpool.py"

if [ ! -f "$FILE" ]; then
  echo "Not found: $FILE"
  exit 1
fi

python3 - "$FILE" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
old = "from adafruit_esp32spi import adafruit_esp32spi as esp32spi"
new = "from .adafruit_esp32spi import SOCKET_CLOSED, SOCKET_LISTEN, SOCKET_FIN_WAIT_1, SOCKET_FIN_WAIT_2, SOCKET_TIME_WAIT, SOCKET_SYN_SENT, SOCKET_SYN_RCVD, SOCKET_CLOSE_WAIT"
if old not in text and new in text:
    print("Already patched:", path)
    sys.exit(0)
if old not in text:
    print("Unexpected file contents, patch manually")
    sys.exit(1)
text = text.replace(old, new)
for name in (
    "SOCKET_LISTEN", "SOCKET_CLOSED", "SOCKET_FIN_WAIT_1", "SOCKET_FIN_WAIT_2",
    "SOCKET_TIME_WAIT", "SOCKET_SYN_SENT", "SOCKET_SYN_RCVD", "SOCKET_CLOSE_WAIT",
):
    text = text.replace("esp32spi." + name, name)
open(path, "w").write(text)
print("Patched:", path)
PY
