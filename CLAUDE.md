# Claude Code Instructions — QuotaPilot

You are working on QuotaPilot.

## Mandatory reading order

Before editing code, read:

1. `docs/TECHNICAL_DESIGN.md`
2. `docs/DECISIONS.md`
3. `docs/HANDOFF.md`
4. the task-specific prompt, if one was provided

Treat `docs/TECHNICAL_DESIGN.md` as the canonical architecture specification.

Treat `docs/HANDOFF.md` as current execution state, not as a substitute for the design.

## Scope discipline

Implement only the requested phase(s).

Do not pre-build future phases merely because the design describes them.

Avoid speculative abstractions and unrelated cleanup.

If the live Codex CLI behavior contradicts the design:

1. inspect and verify actual behavior,
2. capture a sanitized fixture when useful,
3. adapt only the provider boundary,
4. document the discrepancy,
5. do not invent quota semantics.

## Architecture boundaries

Preserve:

```text
CLI -> Services -> Budget / Routing -> Domain
Providers -> Domain
Persistence -> Domain
```

Never introduce:

```text
Domain -> OpenAI
Budget -> Codex RPC
Routing -> SQLite
Provider -> CLI
```

## Testing

For every meaningful change:

- run relevant unit tests,
- run lint,
- run type checking,
- add fixture tests for provider parsing,
- do not require live credentials in normal CI.

## Security

Do not:

- store OpenAI access tokens,
- read browser cookies,
- scrape the ChatGPT UI,
- print secrets,
- commit raw account identifiers or credentials.

Sanitize any live RPC fixture before committing it.

## Handoff requirement

Before ending a meaningful session, update `docs/HANDOFF.md` with:

- completed work,
- current phase,
- changed files,
- exact test commands/results,
- blockers,
- next concrete task.

If you made an architectural decision, append it to `docs/DECISIONS.md`.

Do not claim work is complete unless tests or direct verification support the claim.
