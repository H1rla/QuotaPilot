# Codex Instructions — QuotaPilot

You are working on QuotaPilot, possibly after work performed by Claude Code.

## Mandatory reading order

Before editing:

1. `docs/TECHNICAL_DESIGN.md`
2. `docs/DECISIONS.md`
3. `docs/HANDOFF.md`
4. the current user/task instruction

Do not rely on prior conversational memory in place of these repository files.

## Shared-agent rule

`docs/HANDOFF.md` is the shared current-state window between Claude Code and Codex.

When you finish a meaningful task, update it so another agent can continue without the chat history.

Architectural decisions belong in `docs/DECISIONS.md`.

The canonical design belongs in `docs/TECHNICAL_DESIGN.md`.

## Scope discipline

Implement only the requested phase(s).

Do not rewrite working Claude Code output merely for style.

Review existing tests and architecture before changing an implementation created by another agent.

Prefer minimal, evidence-based changes.

## Architecture boundaries

Preserve:

```text
CLI -> Services -> Budget / Routing -> Domain
Providers -> Domain
Persistence -> Domain
```

Forbidden coupling includes:

```text
Domain -> OpenAI
Budget -> Codex RPC
Routing -> SQLite
Provider -> CLI
```

## Provider behavior

The installed Codex CLI is the source of truth for its current RPC surface.

If behavior differs from the specification:

- verify it,
- save sanitized fixtures where useful,
- document the discrepancy,
- preserve unknown fields,
- do not guess undocumented semantics.

## Verification

Run relevant tests, lint, and type checks.

Normal CI must remain independent of authenticated provider access.

## Security

Never commit credentials, tokens, cookies, raw sensitive account responses, or secrets.

## Handoff

Before stopping, update `docs/HANDOFF.md` with changed files, tests, blockers, and the next action.
