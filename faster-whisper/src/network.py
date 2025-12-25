from __future__ import annotations

import logging
import socket
import time
from typing import Tuple
from urllib.parse import urlparse


def parse_host_port_from_url(url: str) -> Tuple[str, int]:
    u = urlparse(url)
    host = u.hostname or "localhost"
    port = u.port
    if port is None:
        port = 443 if u.scheme == "https" else 80
    return host, port


def wait_for_tcp(host: str, port: int, timeout_s: int, logger: logging.Logger) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except Exception:
            time.sleep(2)
    logger.error("Server not reachable via TCP at %s:%d after %ds", host, port, timeout_s)
    return False
