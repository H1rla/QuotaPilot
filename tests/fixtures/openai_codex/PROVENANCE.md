# Fixture provenance

`codex-cli 0.154.0`, captured/verified 2026-09-18, against a real
authenticated ChatGPT-auth Codex account (plan value not retained) via this repo's own
`AppServerProcess`/`AppServerClient` transport (see
`providers/openai_codex/app_server.py` / `rpc.py`). Schema cross-checked with
`codex app-server generate-json-schema --experimental` (static, offline,
unauthenticated — not itself a fixture source).

Sanitization applied to every live capture before it touched disk: emails,
account IDs, thread IDs, tokens, and similar identifiers were replaced
in-process (never logged in raw form) with clearly-fake placeholders
(`redacted-user@example.invalid`, `acct_redacted_N`). Account plan and
rate-limit telemetry values (percentages, reset timestamps, and related
account-specific values) were also replaced with synthetic values before the
first public Git history was created. Model catalog data
(`model_list.json`) contains no account-identifying information and was
copied verbatim. This same key-based redaction policy (see
`src/quotapilot/providers/openai_codex/redaction.py`) is now applied
automatically, in production, to the raw-observation envelope every live
`capture_usage()` call attaches to `UsageSnapshot.metadata` — it is no
longer just a one-off fixture-generation step.

**2026-09-18 (Phase 2.1 stabilization pass) — `usage_read.json` replaced**:
The version of this fixture committed during Phase 2 contained real
token-usage telemetry (real lifetime/peak/daily token counts and real
usage dates) sanitized only for identifiers, not for the telemetry values
themselves. An independent review flagged this as a privacy problem: token
counts and daily activity are usage telemetry, not just an identifier to
redact. It has been replaced with fully **synthetic** numbers and dates
(schema-shape preserved, including the non-contiguous-buckets property)
that were never real account activity — see the "Synthetic fixtures"
section below.

## Live-verified shapes (account-specific values sanitized or synthesized)

- `account_read.json` — `account/read`. Live-verified shape; email and plan
  values are synthetic placeholders (ChatGPT auth variant retained).
- `rate_limits_single_window.json` — `account/rateLimits/read`. This
  account exposes exactly one metered bucket (`limitId: "codex"`) with only
  a `primary` (weekly, `windowDurationMins: 10080`) window; `secondary` is
  `null`. This is the only rate-limit *shape* available from the account
  used for this session; all account-specific values, including
  `usedPercent` and `resetsAt`, are synthetic/perturbed. No live example of
  a two-window (5h + weekly) account was available.
- `model_list.json` — `model/list`. Real model catalog (6 models) as of
  capture date. `model/list` was not in this session's initial task
  brief but was discovered via schema search and used because design
  §2.1 ranks "provider model catalog" above fallback definitions for
  capability discovery. (This fixture predates pagination support and
  happens to be a single page — `nextCursor: null` — matching the live
  account's real behavior.)

## Synthetic fixtures (schema-conformant, NOT live captures)

These exist to exercise parser branches the live account did not produce.
Constructed by hand against the verified JSON Schema
(`GetAccountRateLimitsResponse` / `RateLimitSnapshot` / `RateLimitWindow` /
`Account`), not observed from a real backend response:

- `rate_limits_multi_window.json` — both `primary` (5h) and `secondary`
  (weekly) windows populated, with `normalModelSlug` set (model-specific
  quota), matching design §14's "5h + weekly" multi-window example.
- `rate_limits_unknown_fields.json` — unrecognized `limitId`, `planType`,
  and `rateLimitReachedType` values, plus extra unmodeled nested fields
  (`futureWindowField`, `futureCreditField`, `futureLimitShape`). Exercises
  "unknown quota category / unknown field must not crash".
- `rate_limits_malformed_percent.json` — `usedPercent: 150` (outside the
  verified 0-100 domain). Exercises explicit validation failure rather than
  silent clamping.
- `rate_limits_no_duration.json` — `resetsAt` present, `windowDurationMins`
  null. Exercises that `starts_at` is left `None` rather than guessed when
  the duration needed to derive it is unavailable.
- `account_read_apikey.json`, `account_read_bedrock.json` — the other two
  `Account` discriminated-union variants (`apiKey`, `amazonBedrock`), which
  this session's live account does not use.
- `account_read_null_account.json` — `GetAccountResponse.account` is
  documented nullable; exercises that branch.
- `usage_read.json` (Phase 2.1: replaced, see note above) — synthetic
  token-usage-history numbers/dates, schema-shape-only. Never real account
  activity. The non-contiguous-dates property (a gap between the first
  bucket and the rest) is preserved intentionally, since that was a real,
  verified backend behavior worth continuing to exercise — the *values*
  around it are invented, not the *shape*.
- `rate_limits_no_windows.json` (Phase 2.1) — a bucket with both `primary`
  and `secondary` null but `credits` populated. Exercises that a bucket
  with no representable window still becomes a pool (preserving its other
  fields) instead of vanishing entirely.
- `model_list_pages.json` (Phase 2.1) — a 2-page `model/list` pagination
  sequence (not a single RPC response — a custom `[{cursor_in, cursor_out,
  data}, ...]` list consumed by the fake peer in
  `tests/unit/test_openai_codex_provider.py`). Page 2 contains a model id
  and reasoning-effort value not present on page 1, to prove pagination
  actually continues and unknown-on-first-page values are preserved. Both
  pages also contain synthetic `catalogVersion`, `paginationHint`, and fake
  `accountId` fields to prove unknown page-level metadata survives capture
  while sensitive identifiers are redacted.
- `model_list_cycle_pages.json` (Phase 2.1) — same custom pagination-list
  format, constructed so page 2's `nextCursor` points back to itself,
  exercising cursor-cycle detection.
