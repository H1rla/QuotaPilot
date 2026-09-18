"""Run core async APIs away from Qt's GUI thread."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class _CoroutineWorker(QRunnable):
    def __init__(self, factory: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        super().__init__()
        self._factory = factory
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = asyncio.run(self._factory())
        except Exception as exc:  # noqa: BLE001 - delivered to the GUI boundary
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(result)


class AsyncRunner(QObject):
    """Own worker lifetimes until their queued Qt signals are delivered."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._active: set[_CoroutineWorker] = set()

    def start(
        self,
        factory: Callable[[], Coroutine[Any, Any, Any]],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        worker = _CoroutineWorker(factory)
        self._active.add(worker)

        def succeeded(result: Any) -> None:
            self._active.discard(worker)
            on_success(result)

        def failed(error: object) -> None:
            self._active.discard(worker)
            on_error(error if isinstance(error, Exception) else RuntimeError("operation failed"))

        worker.signals.succeeded.connect(succeeded)
        worker.signals.failed.connect(failed)
        self._pool.start(worker)
