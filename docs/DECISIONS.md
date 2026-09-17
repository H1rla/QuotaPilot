# QuotaPilot Architecture Decisions

> Append-only log. Do not silently rewrite prior entries — if a decision is
> superseded, add a new dated entry that says so and link back to it.

---

## 2026-09-18 — Domain models are immutable value objects

**Decision**: All `quotapilot.domain` Pydantic models use `ConfigDict(frozen=True)`.

**Why**: `UsageSnapshot` and its components are point-in-time captures that get
persisted and passed through budget/routing layers read-only. Immutability
keeps them boring/deterministic (per design §29) and prevents a downstream
layer from accidentally mutating a shared snapshot.

**Consequence**: Code that needs a modified copy must use Pydantic's
`model_copy(update=...)` rather than in-place mutation.

---

## 2026-09-18 — Fraction/datetime validation strategy in the domain layer

**Decision**: `QuotaPool.used_fraction` / `remaining_fraction` are
`float | None` constrained to `[0.0, 1.0]` via `Field(ge=..., le=...)`
(constraint applies only when a value is present). All "when applicable"
datetimes (`AccountInfo.observed_at`, `QuotaPool.starts_at`/`resets_at`,
`UsageSnapshot.captured_at`) use Pydantic's built-in `AwareDatetime`, which
rejects naive datetimes at validation time.

**Why**: The design (§7.1) requires fractions normalized to 0.0-1.0 "when the
provider exposes enough information" and requires timezone-aware datetimes.
Using `AwareDatetime` instead of a hand-rolled validator avoids duplicating
tzinfo-check logic across five fields.

---

## 2026-09-18 — Verified `codex app-server` transport and RPC surface (codex-cli 0.154.0)

**Context**: TECHNICAL_DESIGN.md §9 lists `account/read` and
`account/rateLimits/read` as "expected current candidates" to be verified
against the installed CLI. This session verified actual behavior of the
locally installed `codex` CLI (`codex-cli 0.154.0`) rather than assuming the
design document was current.

**Verified — method names exist as designed, plus more**:
Running `codex app-server generate-json-schema --experimental --out <dir>`
(a static, offline, non-networked schema dump) confirms these `ClientRequest`
methods exist: `account/read`, `account/rateLimits/read`,
`account/usage/read`, plus `account/login/start`, `account/login/cancel`,
`account/logout`, `account/bedrock/discover`, `account/bedrock/setup`,
`account/rateLimitResetCredit/consume`, `account/workspaceMessages/read`,
`account/sendAddCreditsNudgeEmail`. The design's guessed names were correct.

**Verified — wire transport**: Empirically confirmed (spawned
`codex app-server` with default `--listen stdio://`, sent a raw `initialize`
request, read raw bytes) that the transport is **newline-delimited JSON**:
one JSON object per line, **no `Content-Length` header framing** (unlike
LSP), and **no top-level `"jsonrpc"` field**. Responses echo the request's
`"id"`; server-initiated notifications omit `"id"` entirely and include an
`"emittedAtMs"` timestamp. This is the basis for
`providers/openai_codex/app_server.py` and `rpc.py`.

**Discrepancy — rate-limit response shape differs from a direct fraction**:
`GetAccountRateLimitsResponse` reports usage as `usedPercent: int` (0-100,
**not** a 0.0-1.0 fraction) inside a `RateLimitWindow`. The provider adapter
(Phase 2, not yet implemented) must divide by 100 when normalizing into
`QuotaPool.used_fraction`, and must derive `remaining_fraction` rather than
assume the backend supplies both.

**Discrepancy — no explicit window start**: `RateLimitWindow` has
`resetsAt` (unix seconds, nullable) and `windowDurationMins` (nullable), but
no start timestamp. `QuotaPool.starts_at` must be derived as
`resetsAt - windowDurationMins` when both are present, and left `None`
otherwise — it is not a field the provider gives directly.

**Confirms design's multi-window quota model directly at the provider
boundary**: `GetAccountRateLimitsResponse` exposes both a legacy single
`rateLimits: RateLimitSnapshot` bucket (for backward compatibility) and a
`rateLimitsByLimitId: dict[str, RateLimitSnapshot] | None` keyed by metered
`limit_id` (e.g. `"codex"`). Each `RateLimitSnapshot` has independent
`primary`/`secondary` `RateLimitWindow`s (matching design §14's "5-hour" and
"weekly" pool example) plus optional `credits`/`individualLimit`
(`SpendControlLimitSnapshot`) fields not yet covered by the design — these
should be preserved in `QuotaPool.metadata` rather than dropped when Phase 2
implements the parser.

**Confirms plan-is-metadata-only philosophy**: `Account` is a discriminated
union (`apiKey` | `chatgpt` | `amazonBedrock`); `planType` is only present on
`chatgpt` accounts and enumerates far more than Go/Plus/Pro (`prolite`,
`team`, several `self_serve_business_*`/`enterprise_*`/`edu_*` variants,
`unknown`). This reinforces design §2.1: plan name must stay a fallback
signal, never a branch condition.

**Not implemented in this session**: account/rate-limit parsing and
normalization into domain objects (Phase 2's parser/normalizer). Only the
process lifecycle (`AppServerProcess`) and line-delimited JSON-RPC transport
(`AppServerClient`) were built, per the Phase 2A scope boundary. No live
`account/read` or `account/rateLimits/read` call was made against the user's
real account in this session — only a local, credential-free `initialize`
handshake and the offline schema-generation command were exercised.

**No secrets touched**: `codex app-server generate-json-schema` and the
`initialize` handshake are local, unauthenticated operations. No OpenAI
token, cookie, or account identifier was read, stored, or printed.

---

## 2026-09-18 — Phase 2 parser/normalizer: verified live behavior and mapping decisions

**Context**: This session made live, authenticated `account/read`,
`account/rateLimits/read`, `account/usage/read`, and `model/list` calls
against the user's real, already-authenticated Codex account (ChatGPT auth;
plan value not retained) via this repo's own transport, sanitized every response
in-process before it touched disk, and committed the sanitized results as
fixtures (`tests/fixtures/openai_codex/`, provenance in that directory's
`PROVENANCE.md`).

**New discrepancy — `account/read` requires a `params` key, others don't**:
Calling `account/read` with the `"params"` key entirely absent from the
JSON-RPC envelope fails with `-32600 Invalid request: missing field
'params'`, even though `GetAccountParams`'s own JSON Schema has zero
required fields (so `{}` is a valid params value). `account/rateLimits/read`
and `account/usage/read` both accept an absent/`null` params key without
error (their schema types are `Nullable_Get...Params`, explicitly
nullable). `model/list` behaves like `account/read` — it also requires the
key present (`{}` is fine). The parser/provider code always sends `{}` for
`account/read` and `model/list`, and omits/sends `null` for the other two.
This is a property of the JSON-RPC envelope requirement per-method, not
something derivable from the params schema alone — a future agent adding a
new RPC call should verify this per-method rather than assume schema
optionality implies envelope optionality.

**Decision — `kind="fixed"` for all rate-limit-derived `QuotaPool`s**:
Codex's `RateLimitWindow` has no explicit rolling-vs-fixed flag. We infer
`kind="fixed"` because each window reports one single, global `resetsAt`
for the *whole* window rather than a continuously advancing horizon per
unit of usage — behavior consistent with a hard-reset fixed window, not a
sliding one. This is an inference, not a Codex-declared fact; flagged here
so Phase 4 (budget engine) does not treat it as provider-confirmed truth
without re-checking if Codex ever documents this explicitly.

**Decision — `scope` mapping**: `scope="model"` when
`RateLimitSnapshot.normal_model_slug` is present (Codex's own field,
described as "the model whose display name and reasoning options describe
this quota alias"); `scope="product"` otherwise (an account-wide/category
bucket like the live account's single `"codex"` limit_id, which had
`normal_model_slug: null`). Chosen because it is derived from a
Codex-documented field, not guessed from limit_id string contents.

**Decision — `QuotaPool.starts_at` derivation guarded, not assumed**:
Only computed as `resets_at - window_duration_mins*60` when *both* are
present in the same `RateLimitWindow`; left `None` otherwise (verified live:
the real account's window had both present, but the schema marks both
nullable independently, and a synthetic fixture
(`rate_limits_no_duration.json`) exercises the `None` branch).

**Decision — `QuotaBinding.confidence="provider"` for model-scoped pools**:
`normal_model_slug` is a field Codex itself attaches to the snapshot (not
inferred by QuotaPilot watching usage over time), so bindings derived from
it use `confidence="provider"` rather than `"observed"`.

**New capability-discovery finding — `model/list` exists and was used**:
Prior HANDOFF.md listed "whether Codex exposes a discoverable model
catalog" as an open question. It does: `model/list` (verified live, 6
models returned, including `supportedReasoningEfforts`,
`defaultReasoningEffort`, and `hidden`). `CapabilitySet.models` and
`supports_reasoning_effort` are now populated from this live call rather
than left empty. `supports_model_selection` is inferred as "more than one
selectable model returned" because no explicit Codex flag for this exists
in the verified schema — this is a QuotaPilot-side heuristic over live
data, not a Codex-declared capability, and should be revisited if Codex
ever exposes an explicit flag.

**Not mapped to any domain field — `account/usage/read`**: This RPC
(token-usage history: lifetime/peak/streak stats, daily buckets, optional
per-thread breakdown) has no corresponding domain concept yet — it belongs
to design §20 "Historical usage" (unimplemented, later phase), not to
`UsageSnapshot`/`QuotaPool`. A sanitized fixture was still captured
(`usage_read.json`) for that future phase, but the Phase 2 parser does not
parse it into any domain object. Notably, real `dailyUsageBuckets` are
**not** guaranteed to be contiguous calendar days (verified: a live gap
existed between two bucket dates) — a future history-parsing implementation
must not assume one bucket per day.

**Typed error boundary**: Added `providers/openai_codex/errors.py` with
`CodexTransportError` (process/RPC-transport-layer failures: process won't
start, RPC times out, JSON-RPC error response) and
`CodexNormalizationError` (a structurally-parseable response could not be
turned into a valid domain object — e.g. `usedPercent=150` normalizing to a
fraction outside `[0.0, 1.0]`, which the existing domain `Field(ge=0.0,
le=1.0)` constraint rejects). Deliberately *not* clamped — this fails loudly
per design §30's "do not invent undocumented semantics."

---

## 2026-09-18 — Phase 2.1 stabilization pass (independent review response)

**Context**: An independent Codex review found Phase 3 (persistence) not
ready: the provider boundary could still produce internally-inconsistent
snapshots, silently drop unknown data, overstate confidence in inferred
quota semantics, and had a real fixture-privacy problem. This entry records
what changed and, where it reverses an earlier decision, says so explicitly
rather than silently rewriting it.

### Atomic capture (`capture_usage()`)

**Decision**: Added `OpenAICodexProvider.capture_usage() -> UsageSnapshot`
as the atomic entry point, and added it to the `UsageProvider` Protocol in
`providers/base.py` (provider-neutral — any future provider must implement
it the same way). `get_account()`, `get_quota_pools()`, and
`get_quota_bindings()` now delegate to it rather than each opening their own
independent `app-server` session.

**Why**: The previous per-getter sessions meant a caller building a
`UsageSnapshot` by calling all three separately could observe account,
pools, and bindings from three different points in time — an internally
inconsistent snapshot, exactly what Phase 3 must not persist.

**Consequence**: `get_account()` is now heavier than strictly necessary (it
also fetches and normalizes rate limits and the full model catalog) in
exchange for correctness. `get_models()` remains a standalone lightweight
call — it needs neither account nor rate-limit data, so there's no
coherence hazard for it to solve. `quota_bindings` are derived directly
from the same `pools` list within one `capture_usage()` call
(`normalize_quota_bindings(pools)`), which makes "bindings only reference
pools in the same snapshot" true by construction; `capture_usage()`
re-asserts it defensively (`_check_snapshot_coherence`) rather than
trusting the invariant silently, in case a future edit to either function
drifts them apart.

### Unknown-data preservation and redaction policy

**Decision**: Added `providers/openai_codex/redaction.py` — a small,
denylist-based, key-name redaction function (`redact()`) — and made it a
permanent part of the normalization path, not just a one-off fixture-
sanitization script. Two new preservation envelopes:

- `QuotaPool.metadata["raw_snapshot"]` (already existed) is now passed
  through `redact()` before attachment, defensively, in case Codex ever
  adds a sensitive field inside a `RateLimitSnapshot` (none currently
  observed there).
- `UsageSnapshot.metadata["raw_observation"]` (new field, new envelope):
  redacted `model_dump()`s of the *entire* `account/read` and
  `account/rateLimits/read` raw responses, attached by
  `parser.build_capture_metadata()`. This exists specifically because
  `GetAccountRateLimitsResponse` has top-level fields with no domain
  mapping at all (`rateLimitUpsell`, `rateLimitResetCredits`) that were
  previously silently dropped during normalization — verified: neither
  field was read anywhere in `parser.py` before this pass.
- A bucket with neither `primary` nor `secondary` (e.g. a credits-only
  bucket) previously produced **zero** pools, silently discarding its
  other fields. It now produces one `"...:unrepresented"` `QuotaPool` with
  `kind`/`scope` `"unknown"` and everything preserved in
  `metadata["raw_snapshot"]`, so a future parser version can still find and
  reinterpret it (`_build_unrepresented_quota_pool`).

**Redaction policy** (the concrete answer to "document a redaction
policy"): `redact()` walks the raw structure and replaces any non-null
scalar value whose *key* (case-insensitive) is in a fixed denylist —
`email`, `account_id`/`accountId`, `token`/`access_token`/`refresh_token`/
`id_token`/`api_key`, `session_id`, `thread_id`, `org_id`/
`organization_id`, `workspace_id`, `user_id`, `installation_id` — with the
literal string `"REDACTED"`. Key matching ignores case and separators, and
credential-bearing containers (`authorization`, `password`, `secret`,
`client_secret`, `credentials`, and cookies) are redacted as a whole. It is
a key-name denylist, not a content scanner, and it runs even over values that already came from
`AccountInfo.account_id`/etc. — these envelopes are for preserving
*unknown* structure, not a second authoritative copy of the structured
fields, so redacting them here costs nothing and removes a class of
accidental-leak risk if a future field is added under one of these names.

**Why this is safe to also apply live (not just to fixtures)**: it is a
pure function over already-in-memory response data; it never reads
browser cookies, never touches `~/.codex/auth.json`, and never delays or
skips an actual normalization step — verified via the live integration
test `test_live_capture_usage_is_one_coherent_snapshot`, which asserts the
real account's `accountId` shows up as `"REDACTED"` in the envelope.

### Provenance: walking back `kind="fixed"` and `confidence="provider"`

**This supersedes** the "Decision — `kind=\"fixed\"`..." and "Decision —
`QuotaBinding.confidence=\"provider\"`..." entries above. Those were
already flagged there as inferences, not provider-confirmed facts; this
pass concluded the earlier choices still overstated confidence and
corrected them:

- `QuotaPool.kind` is now **always `"unknown"`** for rate-limit-derived
  pools. `"fixed"` was an inference from a single global `resets_at`
  per window; Codex does not document reset semantics at all, so `"fixed"`
  is no longer asserted anywhere in `parser.py`.
- `QuotaPool.scope` is `"model"` only when `normal_model_slug` is present
  (a genuinely provider-declared fact) — this part is unchanged. The
  fallback case (no model slug) changed from `"product"` to **`"unknown"`**:
  an account-wide metered bucket could equally be `"account"`-scoped, and
  Codex does not say which.
- `QuotaBinding.confidence` changed from `"provider"` to **`"observed"`**:
  `normal_model_slug` is provider-declared, but the *binding* — this exact
  synthesized pool id, grouped this way, applying across all reasoning
  efforts — is QuotaPilot's own construction over that field, not a
  complete binding fact the provider states in one piece. `"provider"` is
  reserved for a (currently nonexistent) RPC that declares a full binding
  directly.

**New mechanism**: every `QuotaPool`/`QuotaBinding` this module builds now
carries `metadata["provenance"]`, a dict from field name to
`{"basis": "provider"|"inferred"|"fallback"|"unknown", "evidence": "..."}`.
This is the extension point the review asked for ("extend domain
confidence/source metadata") — implemented as a `parser.py` convention over
the existing free-form `metadata` field rather than a domain schema change,
since `metadata: dict[str, Any]` already existed on every affected type
except `QuotaBinding` (see below).

**Domain change**: added `metadata: dict[str, Any] = {}` to `QuotaBinding`
(it previously had no metadata field at all, unlike every other domain
type) and to `UsageSnapshot` (for the raw-observation envelope above). Both
additive, non-breaking, and consistent with the existing pattern.

### `model/list` pagination

**Decision**: `OpenAICodexProvider._fetch_all_models()` now loops calling
`model/list` with `{"cursor": <nextCursor>}` until `nextCursor is None`,
within the same session/client used for the rest of a `capture_usage()`
call (or `get_models()`'s own session). Guards: a defensive page limit
(50) and cursor-cycle detection (a repeated `nextCursor` value raises
`CodexNormalizationError` rather than looping forever). Verified live: the
real account's `model/list` returns exactly one page (`nextCursor: null`
immediately), so this loop runs its body exactly once against reality —
confirmed via the live integration suite after this change.

**`includeHidden` decision**: deliberately **not sent** (left at the
server's default, which excludes models hidden from the normal model
picker). Reasoning: QuotaPilot's purpose is recommending a model for
direct use; a model hidden from the normal picker is presumably not meant
to be recommended for direct selection. If a future phase needs the full
catalog (e.g. to explain *why* a model isn't offered), this should be
revisited explicitly rather than silently switched.

### Provider error taxonomy: `CodexRpcError` added

**Decision**: Split what was one `CodexTransportError` catch-all into two:
`CodexTransportError` (process/framing/I-O failures: won't start, EOF,
malformed JSON line, broken pipe, timeout) and `CodexRpcError` (a
well-formed JSON-RPC error response — the transport is fine, the specific
call failed). `CodexRpcError` carries only `method`, `code`, and `message`
— the JSON-RPC error object's `data` field is never propagated or logged,
since a backend could put arbitrary context there QuotaPilot cannot
verify is safe to surface (tested:
`test_rpc_error_response_raises_codex_rpc_error_without_leaking_data`).

**Transport-layer change**: `rpc.AppServerClient` previously left EOF
(closed stdout) and malformed JSON lines unhandled — the read loop just
returned, leaving any pending request to hang until an external caller's
timeout fired (15s in `provider.py`). It now has a new
`AppServerTransportError` and fails every pending request *immediately* on
EOF, a read/write I/O error, or a JSON decode failure, and remembers the
error so any *subsequent* `request()` call fails immediately too instead of
attempting to write into a dead pipe.

### Strict `usedPercent` parsing

**Decision**: `RateLimitWindow.used_percent` is now
`Field(strict=True, ge=0, le=100)` instead of a plain `int`. Pydantic's
lax mode would otherwise silently coerce `"65"` (string) and `65.0`
(float), and — a common Pydantic footgun — accept `True`/`False` for an
`int` field since `bool` is a Python subclass of `int`. The verified JSON
Schema types this field as a plain `integer` with no alternate
representation, so any of those inputs indicates a malformed or
unexpected response, not a value QuotaPilot should coerce.

**Bug fix, not just a decision**: `_unix_seconds_to_datetime` did not
previously handle `datetime.fromtimestamp` overflow — an out-of-range
`resets_at` would have raised a bare, untyped `OverflowError`/`OSError`
straight out of `normalize_quota_pools`, not `CodexNormalizationError`.
Fixed to catch and re-raise as the typed error.

**Explicitly not changed / not invented**: a zero timestamp (`resets_at:
0`) is passed through as Unix epoch rather than treated as a magic
"unknown" sentinel — Codex documents `null` for "no value", not `0`, and
inventing a second meaning for `0` would be exactly the kind of
undocumented-semantics invention design §30 forbids. A zero
`window_duration_mins` is accepted (the domain field's `ge=0` allows it) as
a degenerate but not invalid window where `starts_at == resets_at`.

### Domain immutability: `list` fields became `tuple` fields

**Decision** (resolves MINOR 9's "choose A or B" as a hybrid, smallest-
change fix): `frozen=True` only prevents reassigning a model's top-level
fields — it does not stop `some_model.some_list_field.append(...)` from
mutating a "frozen" instance in place. Converted every list-of-references
field to a `tuple`: `AIModel.supported_efforts`, `CapabilitySet.models`,
`QuotaPool.applies_to_models`, `QuotaBinding.quota_pool_ids`,
`UsageSnapshot.quota_pools`, `UsageSnapshot.quota_bindings`. Since `AIModel`
and `QuotaPool`/`QuotaBinding` are themselves frozen, `CapabilitySet.models`
and `UsageSnapshot.quota_pools`/`quota_bindings` are now genuinely
deep-immutable, not just shallowly so.

**Deliberately not changed**: every `metadata: dict[str, Any]` field.
Making free-form, provider-shaped nested data structures deeply immutable
in Pydantic v2 has no first-class support and would add real complexity
for a field that exists precisely to hold arbitrary, evolving provider
data. Per "prefer the smallest change," this is documented instead
(docstrings on `AIModel`, `QuotaPool`, `QuotaBinding`, `UsageSnapshot`
explicitly say `metadata` is only shallowly immutable and must be treated
as read-only by convention) — Option B for this one field, Option A for
everything else.

**Consequence for callers**: any code (including tests) that previously
compared these fields against list literals (`== []`, `== ["x"]`) or passed
list literals into these specific constructor parameters needed updating
to tuples for `pyright` to accept them (Pydantic itself coerces a `list`
input into a `tuple` field at runtime, so this is a static-typing
requirement, not a runtime one).

### JSON-RPC params: omitted vs. `null` vs. `{}`

**Decision**: `rpc.AppServerClient.request()`'s `params` parameter default
changed from `None` (which meant "omit the key") to a dedicated sentinel,
`OMITTED`. Now `None` means "send an explicit `\"params\": null`", `{}`
means "send an empty object", and `OMITTED` (the default) means "no
`params` key at all" — three states that were previously conflated into
two. `provider.py` updated its call sites accordingly (`account/read` and
`model/list` continue to send `{}`, since both were verified to require the
key present; `account/rateLimits/read` now uses the default `OMITTED`).
Envelope-level tests assert the actual bytes sent for all three states.

### Child stderr draining (deadlock-risk fix, not a lifecycle decision)

**Decision**: `AppServerProcess` now spawns a background task that
continuously drains the child's stderr pipe for the process's entire
lifetime, keeping only a small bounded ring buffer
(`_STDERR_TAIL_LINES = 20`) via `stderr_tail_text()` for future
diagnostics. Previously stderr was piped but never read at all — if
`codex app-server` ever logs enough to fill the OS pipe buffer (~64KB on
Linux), the child would block on its own `write()`, which could deadlock
the whole interaction regardless of QuotaPilot's own behavior. This is
purely a resource-safety fix; it does not decide long-lived-vs-ephemeral
lifecycle (still open, see docs/HANDOFF.md), and `stderr_tail_text()` is
deliberately not yet wired into any exception message — surfacing
arbitrary process log text in errors needs its own redaction-safety
review before that's done, likely alongside a future `quotapilot doctor`.

### Fixture privacy: `usage_read.json` replaced

**Decision**: The Phase 2 version of this fixture sanitized identifiers
but left real token-usage telemetry (real lifetime/peak/daily counts, real
dates) in place. Replaced with fully synthetic numbers/dates; the
non-contiguous-buckets *shape* (a real, verified backend behavior worth
still exercising) was preserved deliberately, the *values* around it were
not. See `tests/fixtures/openai_codex/PROVENANCE.md` for detail and
`tests/unit/test_fixture_hygiene.py` for the new automated regression
guard (scans every fixture for non-placeholder emails/account ids, and
pins the synthetic `usage_read.json` values).

### Final Phase 2.1 provider-boundary hardening

**Strict time fields**: `RateLimitWindow.resets_at` and
`window_duration_mins` now use strict, non-negative integer validation,
matching the verified integer-only provider schema. Strings, booleans,
floats, and negative values are malformed provider data and surface as
`CodexNormalizationError`; they are never coerced. Zero remains valid and
keeps its literal meaning.

**Page-level catalog preservation**: `model/list` pagination now retains
every parsed page in addition to the aggregate model list. A redacted dump of
each page is stored at
`UsageSnapshot.metadata["raw_observation"]["model_list_pages"]`, preserving
unknown top-level fields and pagination metadata independently for every
page. The aggregate is used only for normalized model discovery.

**Capability provenance**: inferred capability values now use the same
metadata convention as quota semantics. `AIModel.selectable`,
`CapabilitySet.supports_model_selection`, `supports_reasoning_effort`, and
`supports_credits` record `source`, `basis`, `confidence`, and explanatory
evidence. These values remain useful heuristics without being presented as
provider-confirmed facts.

**RPC protocol validation**: a decoded app-server line must be a JSON object.
Responses require an integer request ID and exactly one of `result` or a
structured `error` with integer `code` and string `message`; notifications
require a string `method` and no response members. Any violation closes the
client with `AppServerTransportError` and fails all pending requests
immediately. The reader loop also converts any unexpected internal failure
to that typed connection failure, so callers cannot be stranded until an
outer timeout.

**Atomicity wording**: only `capture_usage()` represents one coherent
observation. `get_account()`, `get_quota_pools()`, and
`get_quota_bindings()` each delegate to a separate capture when called
individually, so sequential getter calls are not mutually atomic and must not
be used by persistence.
