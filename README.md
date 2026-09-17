# QuotaPilot

QuotaPilot is a local usage-management and model-routing assistant for
subscription-based AI coding tools (initial target: OpenAI Codex CLI).

It observes quota/rate-limit state, normalizes it into a provider-independent
representation, and recommends an appropriate model and reasoning effort for
a task — without automatically switching models or spending credits.

See `docs/TECHNICAL_DESIGN.md` for the full design and `docs/HANDOFF.md` for
current implementation status.

## Development

```bash
uv sync
uv run quotapilot --help
uv run pytest
uv run ruff check .
uv run pyright
```
