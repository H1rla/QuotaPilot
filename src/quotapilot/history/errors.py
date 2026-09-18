"""Typed errors for the snapshot persistence boundary.

Kept distinguishable so callers don't need to inspect raw `aiosqlite`/
`sqlite3` exceptions (which this layer does not otherwise expose).
"""

from __future__ import annotations


class PersistenceError(Exception):
    """Base for all snapshot-persistence errors."""


class DatabaseInitializationError(PersistenceError):
    """The database could not be opened or its schema could not be established.

    Covers: the database directory/file could not be created or opened, and
    malformed schema-version state, incomplete current-version schemas, and
    version mismatches this build cannot handle.
    """


class SnapshotSerializationError(PersistenceError):
    """A snapshot could not cross the canonical serialization boundary."""


class SnapshotCoherenceError(PersistenceError):
    """A snapshot failed the persistence-boundary coherence check.

    Raised before any write happens — the provider is expected to already
    guarantee this (see `UsageProvider.capture_usage`), but persistence
    re-validates rather than trusting that silently. Never repaired
    automatically; an incoherent snapshot is rejected outright.
    """


class SnapshotWriteError(PersistenceError):
    """Writing a snapshot (and its pool/binding rows) failed.

    The underlying transaction is guaranteed rolled back before this is
    raised — there is never a partially-committed snapshot.
    """


class SnapshotReadError(PersistenceError):
    """A stored snapshot could not be read back as a valid `UsageSnapshot`.

    Covers query failures, malformed stored JSON, and JSON that no longer
    validates against the current domain model.
    """
