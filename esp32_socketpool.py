"""ESP32 SPI socket pool — standalone copy for CircuitPython 8.2.x.

CP 8.2 cannot import adafruit_esp32spi submodules; this file lives at
CIRCUITPY root so `import esp32_socketpool` works.
"""

import errno
import gc
import time

from micropython import const

import adafruit_esp32spi.adafruit_esp32spi as esp32spi

SOCKET_CLOSED = esp32spi.SOCKET_CLOSED
SOCKET_LISTEN = esp32spi.SOCKET_LISTEN
SOCKET_FIN_WAIT_1 = esp32spi.SOCKET_FIN_WAIT_1
SOCKET_FIN_WAIT_2 = esp32spi.SOCKET_FIN_WAIT_2
SOCKET_TIME_WAIT = esp32spi.SOCKET_TIME_WAIT
SOCKET_SYN_SENT = esp32spi.SOCKET_SYN_SENT
SOCKET_SYN_RCVD = esp32spi.SOCKET_SYN_RCVD
SOCKET_CLOSE_WAIT = esp32spi.SOCKET_CLOSE_WAIT

_global_socketpool = {}


class SocketPool:
    SOCK_STREAM = const(1)
    SOCK_DGRAM = const(2)
    AF_INET = const(2)
    SOL_SOCKET = const(0xFFF)
    SO_REUSEADDR = const(0x0004)
    NO_SOCKET_AVAIL = const(255)
    MAX_PACKET = const(4000)

    def __new__(cls, iface):
        if iface not in _global_socketpool:
            _global_socketpool[iface] = super().__new__(cls)
        return _global_socketpool[iface]

    def __init__(self, iface):
        self._interface = iface

    def getaddrinfo(self, host, port, family=0, socktype=0, proto=0, flags=0):
        if not isinstance(port, int):
            raise ValueError("Port must be an integer")
        ipaddr = self._interface.get_host_by_name(host)
        return [(SocketPool.AF_INET, socktype, proto, "", (ipaddr, port))]

    def socket(self, family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None):
        return Socket(self, family, type, proto, fileno)


class Socket:
    def __init__(self, socket_pool, family=SocketPool.AF_INET, type=SocketPool.SOCK_STREAM, proto=0, fileno=None, socknum=None):
        if family != SocketPool.AF_INET:
            raise ValueError("Only AF_INET family supported")
        self._socket_pool = socket_pool
        self._interface = self._socket_pool._interface
        self._type = type
        self._buffer = b""
        self._socknum = socknum if socknum is not None else self._interface.get_socket()
        self._bound = ()
        self.settimeout(None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        while self._interface.socket_status(self._socknum) != SOCKET_CLOSED:
            pass

    def connect(self, address, conntype=None):
        host, port = address
        if conntype is None:
            conntype = (
                self._interface.UDP_MODE
                if self._type == SocketPool.SOCK_DGRAM
                else self._interface.TCP_MODE
            )
        if not self._interface.socket_connect(self._socknum, host, port, conn_mode=conntype):
            raise ConnectionError("Failed to connect to host", host)
        self._buffer = b""

    def send(self, data):
        conntype = (
            self._interface.UDP_MODE
            if self._type == SocketPool.SOCK_DGRAM
            else self._interface.TCP_MODE
        )
        sent = self._interface.socket_write(self._socknum, data, conn_mode=conntype)
        gc.collect()
        return sent

    def sendto(self, data, address):
        self.connect(address)
        return self.send(data)

    def recv(self, bufsize):
        buf = bytearray(bufsize)
        self.recv_into(buf, bufsize)
        return bytes(buf)

    def recv_into(self, buffer, nbytes=0):
        if not 0 <= nbytes <= len(buffer):
            raise ValueError("nbytes must be 0 to len(buffer)")

        last_read_time = time.monotonic_ns()
        num_to_read = len(buffer) if nbytes == 0 else nbytes
        num_read = 0
        while num_to_read > 0:
            if len(self._buffer) > 0:
                bytes_to_read = min(num_to_read, len(self._buffer))
                buffer[num_read : num_read + bytes_to_read] = self._buffer[:bytes_to_read]
                num_read += bytes_to_read
                num_to_read -= bytes_to_read
                self._buffer = self._buffer[bytes_to_read:]
                continue

            num_avail = self._available()
            if num_avail > 0:
                last_read_time = time.monotonic_ns()
                bytes_read = self._interface.socket_read(self._socknum, min(num_to_read, num_avail))
                buffer[num_read : num_read + len(bytes_read)] = bytes_read
                num_read += len(bytes_read)
                num_to_read -= len(bytes_read)
            elif num_read > 0:
                break

            if self._timeout == 0:
                break

            delta = (time.monotonic_ns() - last_read_time) // 1_000_000
            if self._timeout > 0 and delta > self._timeout:
                raise OSError(errno.ETIMEDOUT)
        return num_read

    def settimeout(self, value):
        if value is None:
            self._timeout = -1
        else:
            if value < 0:
                raise ValueError("Timeout cannot be a negative number")
            self._timeout = int(value * 1000)

    def _available(self):
        if self._socknum != SocketPool.NO_SOCKET_AVAIL:
            return min(self._interface.socket_available(self._socknum), SocketPool.MAX_PACKET)
        return 0

    def _connected(self):
        if self._socknum == SocketPool.NO_SOCKET_AVAIL:
            return False
        if self._available():
            return True
        status = self._interface.socket_status(self._socknum)
        result = status not in {
            SOCKET_LISTEN,
            SOCKET_CLOSED,
            SOCKET_FIN_WAIT_1,
            SOCKET_FIN_WAIT_2,
            SOCKET_TIME_WAIT,
            SOCKET_SYN_SENT,
            SOCKET_SYN_RCVD,
            SOCKET_CLOSE_WAIT,
        }
        if not result:
            self.close()
            self._socknum = SocketPool.NO_SOCKET_AVAIL
        return result

    def close(self):
        self._interface.socket_close(self._socknum)

    def accept(self):
        client_sock_num = self._interface.socket_available(self._socknum)
        if client_sock_num != SocketPool.NO_SOCKET_AVAIL:
            sock = Socket(self._socket_pool, socknum=client_sock_num)
            remote = self._interface.get_remote_data(client_sock_num)
            ip_address = "{}.{}.{}.{}".format(*remote["ip_addr"])
            port = remote["port"]
            return sock, (ip_address, port)
        raise OSError(errno.ECONNRESET)

    def bind(self, address):
        self._bound = address

    def listen(self, backlog):
        if not self._bound:
            self._bound = (self._interface.ip_address, 80)
        port = self._bound[1]
        self._interface.start_server(port, self._socknum)

    def setblocking(self, flag):
        if flag:
            self.settimeout(None)
        else:
            self.settimeout(0)

    def setsockopt(self, *opts, **kwopts):
        pass
