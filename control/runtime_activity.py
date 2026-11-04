"""Count accepted HTTP work until it has finished or registered its worker."""
from contextlib import contextmanager
import threading


class RequestActivity:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0

    @contextmanager
    def track(self):
        with self.lock:
            self.active += 1
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1

    def count(self):
        with self.lock:
            return self.active
