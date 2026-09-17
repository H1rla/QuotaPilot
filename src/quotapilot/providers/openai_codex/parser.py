"""Normalizes raw Codex RPC responses (`models.py`) into `quotapilot.domain` types.

```text
provider raw structures (models.py)
        v
this module
        v
QuotaPool / AccountInfo / CapabilitySet / AIModel / QuotaBinding
```

No raw Codex dictionaries escape this module: every public function returns
domain types. Provider quirks (percent-vs-fraction, missing window start,
which account fields exist) are handled here so the domain and any future
budget/routing code never has to know about them.

## Provenance convention

Codex rarely states quota *semantics* explicitly (e.g. whether a window is a
hard-reset fixed window or a continuously rolling one). Every `QuotaPool`
and `QuotaBinding` this module builds carries `metadata["provenance"]`, a
dict from field name to `{"basis": ..., "evidence": ...}` where `basis` is
one of:

- `"provider"` — the value is a direct provider-declared fact.
- `"inferred"` — QuotaPilot derived the value via a documented heuristic
  over provider data; it is not provider-confirmed.
- `"fallback"` — QuotaPilot substituted a bundled/default value.
- `"unknown"` — not knowable from the current data; recorded as such
  rather than guessed.

`kind`/`scope`/`confidence` fields on the domain objects always reflect this
same honesty — `"unknown"` is used whenever provider semantics are not
actually confirmed, even where an earlier version of this module guessed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaBinding, QuotaPool, QuotaScope

from .errors import CodexNormalizationError
from .models import (
    GetAccountRateLimitsResponse,
    GetAccountResponse,
    ModelListResponse,
    RateLimitSnapshot,
    RateLimitWindow,
)
from .redaction import redact

PROVIDER_ID = "openai-codex"

BASIS_PROVIDER = "provider"
BASIS_INFERRED = "inferred"
BASIS_FALLBACK = "fallback"
BASIS_UNKNOWN = "unknown"


def _unix_seconds_to_datetime(value: int | None, *, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise CodexNormalizationError(
            f"{field}={value!r} is not a representable timestamp"
        ) from exc


def _build_quota_pool(
    limit_key: str, snapshot: RateLimitSnapshot, window: RateLimitWindow, label: str
) -> QuotaPool:
    """Normalize one `RateLimitWindow` into a `QuotaPool`.

    `kind` is `"unknown"`: Codex has no rolling-vs-fixed-window flag, and a
    single global `resets_at` is at best suggestive of a fixed window, not
    confirmation — see docs/DECISIONS.md. `scope` is `"model"` only when
    `normal_model_slug` (a provider-declared field) names one; otherwise
    `"unknown"` — a bucket with no model slug could be account-wide or
    product-wide and Codex does not say which.

    `starts_at` is only derived when both `resets_at` and
    `window_duration_mins` are present; Codex never gives a start field
    directly.
    """
    pool_id = f"{limit_key}:{label}"
    used_fraction = window.used_percent / 100.0
    remaining_fraction = 1.0 - used_fraction

    resets_at = _unix_seconds_to_datetime(window.resets_at, field=f"{pool_id}.resets_at")
    window_seconds = (
        window.window_duration_mins * 60 if window.window_duration_mins is not None else None
    )
    starts_at = None
    if window.resets_at is not None and window.window_duration_mins is not None:
        starts_at = _unix_seconds_to_datetime(
            window.resets_at - window.window_duration_mins * 60,
            field=f"{pool_id}.starts_at",
        )

    has_model_slug = bool(snapshot.normal_model_slug)
    scope: QuotaScope = "model" if has_model_slug else "unknown"
    applies_to_models = (snapshot.normal_model_slug,) if snapshot.normal_model_slug else ()

    provenance: dict[str, Any] = {
        "kind": {
            "basis": BASIS_UNKNOWN,
            "evidence": (
                "a single global resets_at was observed for this window; Codex does not "
                "document whether this is a hard-reset fixed window or a continuously "
                "rolling one"
            ),
        },
        "scope": (
            {
                "basis": BASIS_PROVIDER,
                "evidence": f"normal_model_slug={snapshot.normal_model_slug!r} was reported",
            }
            if has_model_slug
            else {
                "basis": BASIS_UNKNOWN,
                "evidence": "no normal_model_slug; could be account-wide or product-wide",
            }
        ),
    }

    metadata: dict[str, Any] = {
        "window": label,
        "provenance": provenance,
        "raw_snapshot": redact(snapshot.model_dump(mode="json", by_alias=True)),
    }

    try:
        return QuotaPool(
            id=pool_id,
            provider=PROVIDER_ID,
            kind="unknown",
            scope=scope,
            used_fraction=used_fraction,
            remaining_fraction=remaining_fraction,
            starts_at=starts_at,
            resets_at=resets_at,
            window_seconds=window_seconds,
            applies_to_models=applies_to_models,
            raw_name=snapshot.limit_name,
            metadata=metadata,
        )
    except ValidationError as exc:
        raise CodexNormalizationError(
            f"quota pool {pool_id!r} failed domain validation "
            f"(used_percent={window.used_percent})"
        ) from exc


def _build_unrepresented_quota_pool(limit_key: str, snapshot: RateLimitSnapshot) -> QuotaPool:
    """A bucket with neither `primary` nor `secondary` still becomes a pool.

    Otherwise its other fields (credits, plan_type, spend-control state,
    ...) would be silently dropped rather than preserved for a future
    parser version to reinterpret.
    """
    pool_id = f"{limit_key}:unrepresented"
    applies_to_models = (snapshot.normal_model_slug,) if snapshot.normal_model_slug else ()
    metadata: dict[str, Any] = {
        "window": "unrepresented",
        "provenance": {
            "kind": {"basis": BASIS_UNKNOWN, "evidence": "no primary/secondary window present"},
            "scope": {"basis": BASIS_UNKNOWN, "evidence": "no primary/secondary window present"},
        },
        "raw_snapshot": redact(snapshot.model_dump(mode="json", by_alias=True)),
    }
    return QuotaPool(
        id=pool_id,
        provider=PROVIDER_ID,
        kind="unknown",
        scope="unknown",
        used_fraction=None,
        remaining_fraction=None,
        starts_at=None,
        resets_at=None,
        window_seconds=None,
        applies_to_models=applies_to_models,
        raw_name=snapshot.limit_name,
        metadata=metadata,
    )


def normalize_quota_pools(response: GetAccountRateLimitsResponse) -> list[QuotaPool]:
    """Normalize `account/rateLimits/read` into `QuotaPool`s.

    Prefers the multi-bucket `rate_limits_by_limit_id` view (one bucket per
    metered `limit_id`) when present; falls back to the legacy single
    `rate_limits` bucket otherwise, keyed by its own `limit_id` (or
    `"default"` if that too is absent). Each bucket contributes up to two
    pools (`primary`/`secondary`); a bucket with neither becomes one
    `"unrepresented"` pool instead of vanishing (see
    `_build_unrepresented_quota_pool`).
    """
    if response.rate_limits_by_limit_id:
        buckets = list(response.rate_limits_by_limit_id.items())
    else:
        key = response.rate_limits.limit_id or "default"
        buckets = [(key, response.rate_limits)]

    pools: list[QuotaPool] = []
    for key, snapshot in buckets:
        windows_found = False
        if snapshot.primary is not None:
            pools.append(_build_quota_pool(key, snapshot, snapshot.primary, "primary"))
            windows_found = True
        if snapshot.secondary is not None:
            pools.append(_build_quota_pool(key, snapshot, snapshot.secondary, "secondary"))
            windows_found = True
        if not windows_found:
            pools.append(_build_unrepresented_quota_pool(key, snapshot))
    return pools


def normalize_quota_bindings(pools: list[QuotaPool]) -> list[QuotaBinding]:
    """Derive many-to-many model<->pool bindings from `QuotaPool.applies_to_models`.

    `confidence="observed"`: `normal_model_slug` is a provider-declared
    field, but the *binding* itself — this exact pool ID, grouped this way,
    applying across all reasoning efforts — is QuotaPilot's own
    construction over that data, not something Codex declares as a binding
    fact in one piece. `"provider"` is reserved for a case where the
    provider RPC surface declares a complete binding directly, which no
    currently verified Codex RPC does. Pools with no known model
    (`applies_to_models == ()`) are simply not bound to anything — no
    binding is fabricated. Only ever produces bindings whose
    `quota_pool_ids` are drawn from `pools`, so a snapshot built from one
    `pools` list is guaranteed internally coherent.
    """
    grouped: dict[str, list[str]] = {}
    for pool in pools:
        for model_id in pool.applies_to_models:
            grouped.setdefault(model_id, []).append(pool.id)
    return [
        QuotaBinding(
            model_id=model_id,
            quota_pool_ids=tuple(pool_ids),
            confidence="observed",
            metadata={
                "provenance": {
                    "basis": BASIS_INFERRED,
                    "evidence": (
                        "derived from RateLimitSnapshot.normal_model_slug "
                        f"(model_id={model_id!r}) on the listed pools; Codex does not "
                        "declare per-effort granularity, so this binding is assumed to "
                        "apply across all reasoning efforts for that model"
                    ),
                }
            },
        )
        for model_id, pool_ids in grouped.items()
    ]


def normalize_models(response: ModelListResponse) -> list[AIModel]:
    """Normalize `model/list` (already fully paginated by the caller) into `AIModel`s.

    `selectable` mirrors `not hidden`. `relative_power`/`relative_cost`/
    `relative_latency` are QuotaPilot's own routing heuristics (design §6.2)
    and are deliberately left `None` here — Codex does not report them.
    """
    models: list[AIModel] = []
    for entry in response.data:
        efforts = tuple(option.reasoning_effort for option in entry.supported_reasoning_efforts)
        try:
            models.append(
                AIModel(
                    id=entry.id,
                    provider=PROVIDER_ID,
                    family=entry.model,
                    selectable=not entry.hidden,
                    supported_efforts=efforts,
                    metadata={
                        "display_name": entry.display_name,
                        "is_default": entry.is_default,
                        "default_reasoning_effort": entry.default_reasoning_effort,
                        "provenance": {
                            "selectable": {
                                "source": "model/list.hidden",
                                "basis": BASIS_INFERRED,
                                "confidence": "high",
                                "evidence": (
                                    f"selectable={not entry.hidden!r} was inferred by negating "
                                    f"the provider-reported hidden={entry.hidden!r} flag"
                                ),
                            }
                        },
                        "raw": redact(entry.model_dump(mode="json", by_alias=True)),
                    },
                )
            )
        except ValidationError as exc:
            raise CodexNormalizationError(
                f"model {entry.id!r} failed domain validation"
            ) from exc
    return models


def normalize_capabilities(
    models: list[AIModel],
    account_response: GetAccountResponse,
    rate_limits_response: GetAccountRateLimitsResponse | None,
) -> CapabilitySet:
    """Build `CapabilitySet` from live discovery only (no plan-name branching).

    `supports_model_selection` is inferred from catalog size (more than one
    selectable model was actually returned) because no explicit Codex flag
    for this was found in the verified schema — see docs/DECISIONS.md.
    """
    reasoning_model_count = sum(1 for model in models if model.supported_efforts)
    selectable_model_count = sum(1 for model in models if model.selectable)
    supports_reasoning_effort = reasoning_model_count > 0

    supports_credits = False
    if rate_limits_response is not None:
        snapshots = (
            list(rate_limits_response.rate_limits_by_limit_id.values())
            if rate_limits_response.rate_limits_by_limit_id
            else [rate_limits_response.rate_limits]
        )
        supports_credits = any(snapshot.credits is not None for snapshot in snapshots)

    metadata: dict[str, Any] = {
        "requires_openai_auth": account_response.requires_openai_auth,
        "provenance": {
            "supports_reasoning_effort": {
                "source": "model/list.data[].supportedReasoningEfforts",
                "basis": BASIS_INFERRED,
                "confidence": "high",
                "evidence": (
                    f"{reasoning_model_count} of {len(models)} returned models advertised "
                    "at least one reasoning-effort option"
                ),
            },
            "supports_model_selection": {
                "source": "model/list.data[].hidden",
                "basis": BASIS_INFERRED,
                "confidence": "medium",
                "evidence": (
                    f"{selectable_model_count} models were inferred selectable; support is "
                    "reported when that count is greater than one"
                ),
            },
            "supports_credits": {
                "source": "account/rateLimits/read.*.credits",
                "basis": BASIS_INFERRED if rate_limits_response is not None else BASIS_UNKNOWN,
                "confidence": "medium" if rate_limits_response is not None else "low",
                "evidence": (
                    "credit support was inferred from the presence of at least one credits "
                    f"structure (present={supports_credits!r})"
                    if rate_limits_response is not None
                    else "rate-limit data was unavailable, so credit support is unknown"
                ),
            },
        },
    }
    if account_response.account is not None:
        metadata["account_type"] = account_response.account.type
    if rate_limits_response is not None:
        metadata["ordinary_usage_allowed"] = rate_limits_response.ordinary_usage_allowed

    return CapabilitySet(
        models=tuple(models),
        supports_reasoning_effort=supports_reasoning_effort,
        supports_credits=supports_credits,
        supports_model_selection=selectable_model_count > 1,
        metadata=metadata,
    )


def normalize_account(
    account_response: GetAccountResponse,
    rate_limits_response: GetAccountRateLimitsResponse | None,
    capabilities: CapabilitySet,
    *,
    observed_at: datetime,
) -> AccountInfo:
    """Normalize `account/read` (+ optionally `account/rateLimits/read`) into `AccountInfo`.

    `account_id` is not present in `GetAccountResponse` at all — Codex only
    exposes it via the rate-limits response's top-level `accountId` — so
    that response is threaded through here when available rather than
    fabricated or omitted.
    """
    plan_name = None
    if account_response.account is not None and account_response.account.type == "chatgpt":
        plan_name = account_response.account.plan_type

    account_id = rate_limits_response.account_id if rate_limits_response is not None else None

    try:
        return AccountInfo(
            provider=PROVIDER_ID,
            account_id=account_id,
            plan_name=plan_name,
            capabilities=capabilities,
            observed_at=observed_at,
        )
    except ValidationError as exc:
        raise CodexNormalizationError("account info failed domain validation") from exc


def build_capture_metadata(
    account_response: GetAccountResponse,
    rate_limits_response: GetAccountRateLimitsResponse,
    model_list_pages: tuple[ModelListResponse, ...],
) -> dict[str, Any]:
    """Snapshot-level envelope preserving top-level fields with no domain mapping.

    Covers fields like `rateLimitUpsell`/`rateLimitResetCredits` (no
    `UsageSnapshot` field exists for them) and any future unknown top-level
    field on either response. Redacted per `redaction.py` before being
    attached — this is *not* the authoritative source for `account_id`
    (that's `AccountInfo.account_id`); it exists only so nothing is
    silently dropped.
    """
    return {
        "raw_observation": {
            "account_read": redact(account_response.model_dump(mode="json", by_alias=True)),
            "rate_limits_read": redact(
                rate_limits_response.model_dump(mode="json", by_alias=True)
            ),
            # Preserve every page independently: rebuilding one aggregate
            # ModelListResponse would otherwise discard unknown top-level
            # page fields and pagination metadata.
            "model_list_pages": [
                redact(page.model_dump(mode="json", by_alias=True)) for page in model_list_pages
            ],
        }
    }
