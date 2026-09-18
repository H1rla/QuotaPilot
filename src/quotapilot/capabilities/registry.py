"""Exact-ID profile registry with deterministic source precedence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from quotapilot.capabilities.errors import AmbiguousProfileError, ProfileLoadError
from quotapilot.capabilities.loader import load_profile
from quotapilot.capabilities.models import (
    ModelProfileDocument,
    ProfileMatch,
    ProvenanceSource,
)

_SOURCE_PRECEDENCE = {
    ProvenanceSource.PROVIDER: 500,
    ProvenanceSource.EMPIRICAL: 400,
    ProvenanceSource.BENCHMARK: 350,
    ProvenanceSource.MANUAL: 300,
    ProvenanceSource.FALLBACK: 100,
    ProvenanceSource.UNKNOWN: 0,
}


class ModelProfileRegistry:
    """Immutable registry; matching is provider + exact model ID only."""

    def __init__(
        self,
        documents: Iterable[tuple[str, ModelProfileDocument]],
    ) -> None:
        index: dict[tuple[str, str], list[tuple[str, ModelProfileDocument]]] = defaultdict(
            list
        )
        for profile_name, document in documents:
            for model_id in document.models:
                index[(document.provider, model_id)].append((profile_name, document))

        for (provider, model_id), entries in index.items():
            seen_priorities: set[int] = set()
            for _name, document in entries:
                source = document.models[model_id].provenance.source
                priority = _SOURCE_PRECEDENCE[source]
                if priority in seen_priorities:
                    raise AmbiguousProfileError(
                        "ambiguous same-precedence profiles for "
                        f"provider={provider!r}, model_id={model_id!r}"
                    )
                seen_priorities.add(priority)

        self._index = {
            key: tuple(
                sorted(
                    entries,
                    key=lambda item: (
                        -_SOURCE_PRECEDENCE[
                            item[1].models[key[1]].provenance.source
                        ],
                        item[0],
                    ),
                )
            )
            for key, entries in index.items()
        }

    @classmethod
    def from_directory(cls, directory: str | Path) -> ModelProfileRegistry:
        profile_dir = Path(directory)
        if not profile_dir.is_dir():
            raise ProfileLoadError("model profile directory does not exist")
        paths = sorted((*profile_dir.glob("*.yaml"), *profile_dir.glob("*.yml")))
        if not paths:
            raise ProfileLoadError("model profile directory contains no YAML profiles")
        return cls((path.name, load_profile(path)) for path in paths)

    def matches(
        self,
        provider: str,
        model_id: str,
        *,
        evaluated_on: date,
    ) -> tuple[ProfileMatch, ...]:
        """Return exact matches in descending provenance precedence."""
        entries = self._index.get((provider, model_id), ())
        return tuple(
            ProfileMatch(
                provider=provider,
                product=document.product,
                model_id=model_id,
                schema_version=document.schema_version,
                verified_at=document.verified_at,
                expires_after_days=document.expires_after_days,
                freshness=document.freshness(evaluated_on),
                profile=document.models[model_id],
                profile_name=profile_name,
            )
            for profile_name, document in entries
        )
