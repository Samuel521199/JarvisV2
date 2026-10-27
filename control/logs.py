"""Local diagnostic log (standard library only).

One rotating file per data root at ``<data-root>/logs/jarvis.log`` (2 MB x 5).
Log codes, identifiers and exception types for diagnosis. Never log credentials,
prompts, replies, mail bodies or memory content: the log is a plain local file.
"""
from __future__ import annotations

import logging
import logging.handlers
import threading
import time

from control.paths import child, data_root

ROOT_LOGGER = 'jarvis'
logging.getLogger(ROOT_LOGGER).addHandler(logging.NullHandler())  # quiet until configured

_configured: set[str] = set()
_guard = threading.Lock()
_last: dict[str, float] = {}


def configure(root, level=logging.INFO):
    """Attach the rotating file (and a stderr echo for warnings) once per data root."""
    root = data_root(root)
    with _guard:
        if str(root) in _configured:
            return child(root, 'logs/jarvis.log')
        folder = child(root, 'logs'); folder.mkdir(exist_ok=True)
        path = child(root, 'logs/jarvis.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s')
        file_handler = logging.handlers.RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(formatter)
        console = logging.StreamHandler(); console.setLevel(logging.WARNING); console.setFormatter(formatter)
        logger = logging.getLogger(ROOT_LOGGER)
        logger.setLevel(level); logger.addHandler(file_handler); logger.addHandler(console)
        logger.propagate = False
        _configured.add(str(root))
        return path


def get(name: str) -> logging.Logger:
    return logging.getLogger(ROOT_LOGGER + '.' + name)


def throttled(logger: logging.Logger, key: str, message: str, *args, interval: float = 60.0, level=logging.WARNING, exc_info=True):
    """Log a recurring failure at most once per interval (loops poll every 100 ms)."""
    now = time.monotonic()
    with _guard:
        if now - _last.get(key, -interval) < interval:
            return False
        _last[key] = now
    logger.log(level, message, *args, exc_info=exc_info)
    return True
