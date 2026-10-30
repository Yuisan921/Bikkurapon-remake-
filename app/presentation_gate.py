"""Hold one physical draw until its display reports the end of the animation."""

import threading


class PresentationGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending = None
        self._cancelled = set()

    def wait(self, reservation_id, publish, timeout):
        done = threading.Event()
        with self._lock:
            if self._pending is not None:
                return False
            self._pending = (reservation_id, done)
        try:
            publish()
            signalled = done.wait(timeout)
            with self._lock:
                cancelled = reservation_id in self._cancelled
            return signalled and not cancelled
        finally:
            with self._lock:
                self._pending = None

    def complete(self, reservation_id):
        with self._lock:
            if self._pending is None or self._pending[0] != reservation_id:
                return False
            self._pending[1].set()
            return True

    def cancel(self):
        """待機中の演出を排出せずに解除し、予約番号を返す。"""
        with self._lock:
            if self._pending is None:
                return None
            reservation_id, done = self._pending
            self._cancelled.add(reservation_id)
            done.set()
            return reservation_id

    def consume_cancelled(self, reservation_id):
        """指定した待機が管理画面から中止されたかを一度だけ返す。"""
        with self._lock:
            if reservation_id not in self._cancelled:
                return False
            self._cancelled.remove(reservation_id)
            return True

    @property
    def busy(self):
        with self._lock:
            return self._pending is not None
