"""Privacy-safe capability list over the persisted snapshot and profile registry."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from quotapilot.capabilities.enrichment import CapabilityEnricher, capability_views
from quotapilot.capabilities.models import ModelCapabilityView
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.history.repository import SnapshotRepository


@dataclass(frozen=True, slots=True)
class ModelRow:
    view: ModelCapabilityView
    supported_efforts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelsState:
    status: str = "empty"
    models: tuple[ModelRow, ...] = ()
    message_id: str | None = None


class ModelsViewModel:
    def __init__(
        self,
        repository: SnapshotRepository | None,
        enricher: CapabilityEnricher | None,
        registry: ModelProfileRegistry | None,
        provider: str | None,
    ) -> None:
        self._repository = repository
        self._enricher = enricher
        self._registry = registry
        self._provider = provider
        self.state = ModelsState()
        self.active = False

    async def load(self, publish: Callable[[ModelsState], None] | None = None) -> ModelsState:
        if self.active:
            return self.state
        self.active = True
        self.state = ModelsState(status="loading")
        if publish is not None:
            publish(self.state)
        try:
            if self._repository is None or self._enricher is None or self._registry is None:
                raise RuntimeError("models dependencies unavailable")
            snapshot = await self._repository.get_latest_snapshot(provider=self._provider)
            if snapshot is None:
                self.state = ModelsState(message_id="models.no_snapshot")
            else:
                # Profile merging and row projection are synchronous CPU work;
                # keep them off Textual's event loop for a large model catalog.
                enriched = await asyncio.to_thread(
                    self._enricher.enrich,
                    snapshot.account.capabilities,
                    self._registry,
                    evaluated_on=datetime.now(UTC).date(),
                )
                views = await asyncio.to_thread(capability_views, enriched)
                by_id = {model.id: model for model in enriched.models}
                self.state = ModelsState(
                    status="ready",
                    models=tuple(
                        ModelRow(view, by_id[view.model_id].supported_efforts) for view in views
                    ),
                )
        except Exception:  # noqa: BLE001 - privacy-safe UI error
            self.state = ModelsState(status="error", message_id="models.error")
        finally:
            self.active = False
        return self.state
