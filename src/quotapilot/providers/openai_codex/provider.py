"""Concrete OpenAI Codex `UsageProvider` adapter.

```text
RPC (AppServerProcess / AppServerClient)
        v
raw response models (models.py)
        v
parser.py
        v
normalized domain objects
```

Quota-policy math (pacing, reserves, escalation, routing) does not belong
here — this adapter only fetches and normalizes. It satisfies
`quotapilot.providers.base.UsageProvider` as far as the currently verified
RPC surface permits (see docs/DECISIONS.md and docs/HANDOFF.md for what
remains undiscoverable, e.g. per-effort quota bindings).

`capture_usage()` is the only coherent snapshot entry point: one
`app-server` session, one shared `captured_at`, one `UsageSnapshot`.
Individual getters delegate to separate capture calls and therefore remain
independent observations when invoked sequentially; persistence must call
`capture_usage()` directly rather than combine getter results.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from quotapilot import __version__
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaBinding, QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.providers.base import (
    ProviderAuthentication,
    ProviderConnection,
    ProviderHealth,
    ProviderInspection,
)

from .app_server import AppServerNotRunningError, AppServerProcess
from .errors import CodexNormalizationError, CodexRpcError, CodexTransportError
from .models import (
    CodexModelEntry,
    GetAccountRateLimitsResponse,
    GetAccountResponse,
    ModelListResponse,
    parse_codex_response,
)
from .parser import (
    PROVIDER_ID,
    build_capture_metadata,
    normalize_account,
    normalize_capabilities,
    normalize_models,
    normalize_quota_bindings,
    normalize_quota_pools,
)
from .rpc import OMITTED, AppServerClient, AppServerRpcError, AppServerTransportError, OmittedType

_CLIENT_INFO = {"name": "quotapilot", "version": __version__}
_RPC_TIMEOUT_SECONDS = 15
_START_TIMEOUT_SECONDS = 10
_MAX_MODEL_LIST_PAGES = 50

# We deliberately do not request `includeHidden` for `model/list`: the
# server-side default excludes models hidden from the normal picker, which
# matches what a routing/recommendation engine should offer — a model
# hidden from the picker is presumably not meant to be recommended for
# direct selection. See docs/DECISIONS.md.


class OpenAICodexProvider:
    """`UsageProvider` implementation backed by `codex app-server`.

    Each public method opens an ephemeral `codex app-server` process for the
    duration of the call and tears it down afterward — matching the CLI's
    own "ephemeral" mode observed via `codex doctor` when no background
    daemon is running. Whether QuotaPilot should instead reuse a long-lived
    daemon is an open question (see docs/HANDOFF.md), deliberately not
    decided here to avoid adding caching/lifecycle policy to an adapter.
    """

    def __init__(
        self,
        *,
        codex_executable: str = "codex",
        codex_args: Sequence[str] = ("app-server",),
    ) -> None:
        self._codex_executable = codex_executable
        self._codex_args = tuple(codex_args)

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AppServerClient]:
        process = AppServerProcess(executable=self._codex_executable, args=self._codex_args)
        try:
            await asyncio.wait_for(process.start(), timeout=_START_TIMEOUT_SECONDS)
        except (OSError, TimeoutError) as exc:
            raise CodexTransportError(
                f"failed to start '{self._codex_executable}' with args {self._codex_args!r}"
            ) from exc

        client = AppServerClient(process)
        client.start_reading()
        try:
            await self._call(client, "initialize", {"clientInfo": _CLIENT_INFO})
            yield client
        finally:
            # Process cleanup must still run if a reader task ever fails
            # while it is being stopped.
            try:
                await client.stop_reading()
            finally:
                await process.stop()

    async def _call(
        self,
        client: AppServerClient,
        method: str,
        params: dict[str, Any] | None | OmittedType = OMITTED,
    ) -> object:
        try:
            return await asyncio.wait_for(
                client.request(method, params), timeout=_RPC_TIMEOUT_SECONDS
            )
        except AppServerRpcError as exc:
            raise CodexRpcError(method=method, code=exc.code, message=exc.message) from exc
        except TimeoutError as exc:
            raise CodexTransportError(f"{method} timed out") from exc
        except (AppServerNotRunningError, AppServerTransportError, OSError) as exc:
            raise CodexTransportError(f"{method} failed: {exc}") from exc

    async def _fetch_account_response(self, client: AppServerClient) -> GetAccountResponse:
        raw = await self._call(client, "account/read", {})
        return parse_codex_response(GetAccountResponse, raw, context="account/read")

    async def _fetch_rate_limits_response(
        self, client: AppServerClient
    ) -> GetAccountRateLimitsResponse:
        raw = await self._call(client, "account/rateLimits/read")
        return parse_codex_response(
            GetAccountRateLimitsResponse, raw, context="account/rateLimits/read"
        )

    async def _fetch_model_list_page(
        self, client: AppServerClient, cursor: str | None
    ) -> ModelListResponse:
        params: dict[str, Any] = {"cursor": cursor} if cursor is not None else {}
        raw = await self._call(client, "model/list", params)
        return parse_codex_response(ModelListResponse, raw, context="model/list")

    async def _fetch_all_models(
        self, client: AppServerClient
    ) -> tuple[ModelListResponse, tuple[ModelListResponse, ...]]:
        """Fully paginate `model/list`, continuing until `nextCursor is None`.

        Guards against a misbehaving server with a defensive page limit and
        cursor-cycle detection — a repeated cursor would otherwise loop
        forever. Returns both the normalized aggregate and every original
        page so capture metadata can preserve unknown page-level fields.
        """
        all_entries: list[CodexModelEntry] = []
        pages: list[ModelListResponse] = []
        seen_cursors: set[str] = set()
        cursor: str | None = None

        for _page_number in range(1, _MAX_MODEL_LIST_PAGES + 1):
            page = await self._fetch_model_list_page(client, cursor)
            pages.append(page)
            all_entries.extend(page.data)
            next_cursor = page.next_cursor
            if next_cursor is None:
                return (
                    ModelListResponse(data=all_entries, next_cursor=None),
                    tuple(pages),
                )
            if next_cursor in seen_cursors:
                raise CodexNormalizationError(
                    f"model/list pagination cursor cycle detected (cursor={next_cursor!r})"
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        raise CodexNormalizationError(
            f"model/list pagination exceeded the defensive page limit "
            f"({_MAX_MODEL_LIST_PAGES})"
        )

    @staticmethod
    def _check_snapshot_coherence(
        pools: list[QuotaPool], bindings: list[QuotaBinding]
    ) -> None:
        pool_ids = {pool.id for pool in pools}
        for binding in bindings:
            unknown = [pid for pid in binding.quota_pool_ids if pid not in pool_ids]
            if unknown:
                raise CodexNormalizationError(
                    f"binding for model {binding.model_id!r} references pool id(s) "
                    f"{unknown!r} not present in this capture's quota pools"
                )

    async def capture_usage(self) -> UsageSnapshot:
        """Atomically capture account, capabilities, quota pools, and bindings.

        Everything comes from one `app-server` session and shares one
        `captured_at` timestamp. `quota_bindings` are derived directly from
        `quota_pools` (see `parser.normalize_quota_bindings`), so they are
        structurally guaranteed to reference only pools in this same
        snapshot — `_check_snapshot_coherence` re-asserts that as a
        defensive check rather than trusting the invariant silently.
        """
        async with self._session() as client:
            captured_at = datetime.now(UTC)
            account_response = await self._fetch_account_response(client)
            rate_limits_response = await self._fetch_rate_limits_response(client)
            model_list_response, model_list_pages = await self._fetch_all_models(client)

        models = normalize_models(model_list_response)
        capabilities = normalize_capabilities(models, account_response, rate_limits_response)
        account = normalize_account(
            account_response,
            rate_limits_response,
            capabilities,
            observed_at=captured_at,
        )
        pools = normalize_quota_pools(rate_limits_response)
        bindings = normalize_quota_bindings(pools)
        self._check_snapshot_coherence(pools, bindings)

        return UsageSnapshot(
            account=account,
            quota_pools=tuple(pools),
            quota_bindings=tuple(bindings),
            captured_at=captured_at,
            metadata=build_capture_metadata(
                account_response,
                rate_limits_response,
                model_list_pages,
            ),
        )

    async def get_account(self) -> AccountInfo:
        snapshot = await self.capture_usage()
        return snapshot.account

    async def get_models(self) -> list[AIModel]:
        async with self._session() as client:
            model_list_response, _model_list_pages = await self._fetch_all_models(client)
        return normalize_models(model_list_response)

    async def get_quota_pools(self) -> list[QuotaPool]:
        snapshot = await self.capture_usage()
        return list(snapshot.quota_pools)

    async def get_quota_bindings(self) -> list[QuotaBinding]:
        snapshot = await self.capture_usage()
        return list(snapshot.quota_bindings)

    async def healthcheck(self) -> ProviderHealth:
        try:
            async with self._session():
                pass
        except (CodexTransportError, CodexRpcError) as exc:
            return ProviderHealth(
                provider=PROVIDER_ID,
                ok=False,
                detail=str(exc),
                checked_at=datetime.now(UTC),
            )
        return ProviderHealth(
            provider=PROVIDER_ID,
            ok=True,
            detail=None,
            checked_at=datetime.now(UTC),
        )

    async def inspect_status(self) -> ProviderInspection:
        """Inspect Codex connectivity/auth without exposing account metadata."""
        checked_at = datetime.now(UTC)
        try:
            async with self._session() as client:
                account = await self._fetch_account_response(client)
        except (CodexTransportError, CodexRpcError, CodexNormalizationError):
            return ProviderInspection(
                provider=PROVIDER_ID,
                connection=ProviderConnection.UNAVAILABLE,
                authentication=ProviderAuthentication.UNKNOWN,
                checked_at=checked_at,
            )
        if account.account is not None:
            authentication = ProviderAuthentication.AUTHENTICATED
        elif account.requires_openai_auth:
            authentication = ProviderAuthentication.NOT_AUTHENTICATED
        else:
            # No account and no login requirement is not enough evidence to
            # claim either an authenticated or unauthenticated account.
            authentication = ProviderAuthentication.UNKNOWN
        return ProviderInspection(
            provider=PROVIDER_ID,
            connection=ProviderConnection.CONNECTED,
            authentication=authentication,
            checked_at=checked_at,
        )
