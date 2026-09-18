"""Provider-independent snapshot persistence (Phase 3).

```text
UsageSnapshot -> SnapshotRepository -> SQLite
```

This package must depend only on `quotapilot.domain` — never on
`quotapilot.providers` (no OpenAI/Codex imports) and never on
`quotapilot.cli`.
"""
