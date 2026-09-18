"""Capture a snapshot from a provider and persist it.

```text
provider.capture_usage() -> repository.save_snapshot()
```

No budget/routing/policy logic belongs here — see design §27's dependency
boundary. This module only calls `Providers -> Domain` and
`Persistence -> Domain`; it never lets a provider call persistence directly
or vice versa.
"""

from __future__ import annotations

from dataclasses import dataclass

from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.repository import SnapshotRepository
from quotapilot.providers.base import UsageProvider


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    """The assigned id plus the captured in-memory snapshot.

    Persistence may replace structured account identity with a pseudonymous
    local correlation key without mutating this object.
    """

    id: int
    snapshot: UsageSnapshot


class SnapshotService:
    """Orchestrates one provider capture followed by one repository save."""

    def __init__(self, provider: UsageProvider, repository: SnapshotRepository) -> None:
        self._provider = provider
        self._repository = repository

    async def capture_and_store(self) -> StoredSnapshot:
        snapshot = await self._provider.capture_usage()
        snapshot_id = await self._repository.save_snapshot(snapshot)
        return StoredSnapshot(id=snapshot_id, snapshot=snapshot)
