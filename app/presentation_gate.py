"""Hold one physical draw until its display reports the end of the animation."""

import threading


class PresentationGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending = None

    def wait(self, reservation_id, publish, timeout):
        done = threading.Event()
        with self._lock:
            if self._pending is not None:
                return False
            self._pending = (reservation_id, done)
        try:
            publish()
            return done.wait(timeout)
        finally:
            with self._lock:
                self._pending = None

    def complete(self, reservation_id):
        with self._lock:
            if self._pending is None or self._pending[0] != reservation_id:
                return False
            self._pending[1].set()
            return True

    @property
    def busy(self):
        with self._lock:
            return self._pending is not None
