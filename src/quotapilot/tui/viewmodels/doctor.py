"""Offline Doctor runner isolated from Textual's event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from quotapilot.observability.doctor import DoctorReport, DoctorService
from quotapilot.tui.state import ViewStatus


@dataclass(frozen=True, slots=True)
class DoctorState:
    status: ViewStatus = ViewStatus.INITIAL
    report: DoctorReport | None = None
    message_id: str | None = None


class DoctorViewModel:
    def __init__(self, service: DoctorService) -> None:
        self._service = service
        self.state = DoctorState()
        self.active = False

    async def load(self, publish: Callable[[DoctorState], None]) -> DoctorState:
        if self.active:
            return self.state
        self.active = True
        self.state = DoctorState(ViewStatus.LOADING, self.state.report, "doctor.running")
        publish(self.state)
        try:
            # Doctor's fixed-argument CLI checks are synchronous; isolate them.
            report = await asyncio.to_thread(
                lambda: asyncio.run(self._service.run(now=datetime.now(UTC), live=False))
            )
            self.state = DoctorState(ViewStatus.READY, report)
        except Exception:  # noqa: BLE001 - stable diagnostic presentation
            self.state = DoctorState(ViewStatus.ERROR, self.state.report, "doctor.error")
        finally:
            self.active = False
        publish(self.state)
        return self.state
