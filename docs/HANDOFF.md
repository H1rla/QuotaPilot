# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 2.1 provider-boundary stabilization complete**
- Phase 2 readiness: **COMPLETE**
- Phase 3 readiness: **READY**
- Phase 3 persistence: **not started**
- Dependency direction: `providers -> domain`; no domain import of provider code

`OpenAICodexProvider.capture_usage()` is the only coherent observation API.
Persistence must use it directly. Sequential calls to `get_account()`,
`get_quota_pools()`, and `get_quota_bindings()` are separate observations.

## Final Phase 2.1 work

- Added one-session atomic snapshot capture with one `captured_at` and a
  binding-to-pool coherence check.
- Preserved unknown account/rate-limit data and every individual
  `model/list` page under redacted capture metadata. Page-level unknown and
  pagination fields survive normalization.
- Corrected unconfirmed quota semantics to `unknown`/`observed` and recorded
  provenance. Inferred model/capability values record `source`, `basis`,
  `confidence`, and evidence.
- Fully paginated `model/list` with cursor-cycle and page-count guards. Model
  IDs and reasoning efforts remain open strings; no catalog is hardcoded into
  plan logic.
- Split transport, RPC, and normalization errors. JSON values that are not
  objects and malformed response/error envelopes now fail pending requests
  immediately with a typed transport error.
- Made `usedPercent`, `resetsAt`, and `windowDurationMins` strict integers;
  percentages are bounded to 0–100 and time values are non-negative. Invalid
  provider shapes become `CodexNormalizationError`.
- Distinguished omitted, null, and empty-object RPC params. `account/read`
  and `model/list` explicitly send `{}`; tolerant methods may omit params.
- Converted domain collection fields to tuples. Free-form metadata remains
  shallowly immutable by documented contract and must be copied defensively
  if a persistence implementation may mutate it.
- Continuously drains bounded child stderr and reliably stops the subprocess
  even when reader cleanup fails. Long-lived versus ephemeral lifecycle is
  intentionally still undecided.
- Sanitized all fixtures before public history: identifiers are placeholders,
  `usage_read.json` is synthetic, and account plan/rate-limit telemetry values
  are synthetic/perturbed. Fixture hygiene tests guard these properties.
- Expanded raw-observation redaction to normalize snake/camel/hyphenated key
  variants and redact credential-bearing containers as a whole.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/test_openai_codex_live.py -v
```

Results:

- Offline/default pytest: **134 passed, 4 skipped** in 0.71s. The four skipped
  tests are the opt-in authenticated integration suite.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- CLI: `quotapilot --help` completed successfully.
- Live integration: **4 passed** in 1.94s against the already-authenticated
  Codex CLI. No credential, account identifier, or raw response was printed or
  written.

Normal tests remain offline and use fixtures/fake stdio peers. Live tests still
require `QUOTAPILOT_INTEGRATION=1`.

## Privacy/security state

- No credentials, tokens, cookies, real email/account/session/org identifiers,
  or live private usage telemetry belong in the clean tree.
- `tests/fixtures/openai_codex/PROVENANCE.md` records which shapes were
  live-verified and exactly which values are synthetic or sanitized.
- Runtime raw-observation metadata is key-redacted before it enters the domain
  snapshot. This redacted metadata is safe enough for Phase 3 persistence;
  never persist a pre-redaction provider response.
- The pre-publication local Git history contained an obsolete version of real
  usage telemetry. It was not pushed: publication used a fresh root commit
  made only from the sanitized working tree, and the isolated obsolete Git
  object database was removed after the clean commit succeeded.

## Git publication

- Target branch: `main`
- Remote: `git@github.com:H1rla/QuotaPilot.git`
- Remote inspection: empty before initial publication
- Clean-history initialization: **complete**; fresh `main` root only
- Initial commit: `025150f3273b239831ee06a7a051981abb5c7dec`
- Initial commit message: `feat: establish Codex provider foundation`
- Initial push: **SUCCESS**; local `main` tracks `origin/main`

## Known risks / deferred decisions

- The provider still launches an ephemeral `codex app-server` per capture.
  Long-lived versus ephemeral lifecycle remains explicitly deferred.
- The live account exposes only one weekly quota window. Multi-window,
  model-scoped, no-window, and multi-page catalog cases are fixture-tested.
- Free-form `metadata` dictionaries are shallowly immutable. Phase 3 should
  serialize or copy them without mutating the snapshot.
- Redaction is key-based, not a content/entropy scanner. New provider fields
  with novel sensitive key names require review.
- `account/usage/read` has no domain mapping and is not part of current capture.

## Next task

Begin **Phase 3 snapshot persistence** only when explicitly requested. Persist
the coherent result of `capture_usage()` and its already-redacted metadata; do
not reconstruct a snapshot from individual getters. Do not begin budget,
pacing, or routing work yet.
