"""Provider-independent snapshot repository protocol.

No OpenAI/Codex import belongs in this module, or anywhere in
`quotapilot.history` — persistence only ever sees `quotapilot.domain`
types, never provider-specific RPC shapes.
"""

from __future__ import annotations

from typing import Protocol

from quotapilot.domain.usage import UsageSnapshot


class SnapshotRepository(Protocol):
    """Stores and reconstructs `UsageSnapshot`s.

    Implementations must treat `UsageSnapshot` as the maximum information
    boundary allowed into persistence: they must never reach back into raw
    provider/transport responses, must pseudonymize any structured raw account
    identifier without mutating the caller's object, and must reject (not
    repair) incoherent provider/pool/binding identity.
    """

    async def save_snapshot(self, snapshot: UsageSnapshot) -> int:
        """Persist one privacy-safe canonical copy atomically; return its id."""
        ...

    async def get_snapshot(self, snapshot_id: int) -> UsageSnapshot | None:
        """Return the snapshot with `snapshot_id`, or `None` if it doesn't exist."""
        ...

    async def get_latest_snapshot(self, provider: str | None = None) -> UsageSnapshot | None:
        """Return the most recently captured snapshot (optionally filtered by provider)."""
        ...

    async def list_snapshots(
        self,
        *,
        provider: str | None = None,
        limit: int = 100,
    ) -> tuple[UsageSnapshot, ...]:
        """Return up to `limit` snapshots, newest first (optionally filtered by provider)."""
        ...
