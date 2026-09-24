"""Session-only advisory route state over the Phase 5 service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from quotapilot.routing.errors import NoRoutableModelError
from quotapilot.services.routing import RoutingContext, RoutingService


@dataclass(frozen=True, slots=True)
class RouteState:
    status: str = "empty"
    context: RoutingContext | None = None
    message_id: str | None = None


class RouteViewModel:
    def __init__(self, service: RoutingService | None, provider: str | None) -> None:
        self._service = service
        self._provider = provider
        self.task = ""
        self.state = RouteState()
        self.active = False

    def set_task(self, task: str) -> None:
        if task != self.task:
            self.task = task
            self.state = RouteState()

    async def analyze(self, publish: Callable[[RouteState], None] | None = None) -> RouteState:
        if self.active:
            return self.state
        if not self.task.strip():
            self.state = RouteState(message_id="route.empty")
            return self.state
        self.active = True
        self.state = RouteState(status="analyzing")
        if publish is not None:
            publish(self.state)
        analyzed_task = self.task.strip()
        try:
            if self._service is None:
                raise RuntimeError("routing service unavailable")
            context = await self._service.recommend_latest_context(
                analyzed_task,
                now=datetime.now(UTC),
                provider=self._provider,
            )
            if self.task.strip() == analyzed_task:
                self.state = (
                    RouteState(status="ready", context=context)
                    if context is not None
                    else RouteState(status="unavailable", message_id="route.no_snapshot")
                )
        except NoRoutableModelError:
            if self.task.strip() == analyzed_task:
                self.state = RouteState(status="unavailable", message_id="route.no_model")
        except Exception:  # noqa: BLE001 - presentation boundary suppresses raw provider data
            if self.task.strip() == analyzed_task:
                self.state = RouteState(status="error", message_id="route.error")
        finally:
            self.active = False
        return self.state
