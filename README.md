# QuotaPilot

QuotaPilot is a local-first quota observer, budget advisor, model router, and
policy-gated execution tool for subscription AI coding tools. The initial
provider is the OpenAI Codex CLI.

It turns provider quota observations into a provider-neutral snapshot, stores
privacy-safe history locally, estimates quota pace, recommends a model and
reasoning effort, and can prepare or run a bounded execution plan. Unknown or
stale inputs remain visible instead of being treated as free or unlimited
quota.

## Current status

QuotaPilot is a pre-1.0 Linux-tested project. Its provider, persistence,
budget, routing, capability-profile, controlled-execution, and product CLI
boundaries are implemented. Routing coefficients and bundled model profiles
are deterministic and reviewable, but remain heuristic and provisionally
calibrated.

## Key features

- Atomic Codex quota and model-capability capture.
- Local SQLite history with pseudonymized account correlation.
- Conservative budget pace, reserve, daily allocation, stale-data warnings,
  and multi-window pressure.
- Capability-driven, quota-aware advisory routing with explainable scores and
  escalation paths.
- Versioned, provenance-bearing model profiles and deterministic calibration.
- Dry-run-first, explicitly authorized Codex execution with live quota and
  capability revalidation, timeouts, bounded output, and bounded escalation.
- Privacy-safe `status`, `models`, `doctor`, and Waybar JSON surfaces.

## Safety and privacy

QuotaPilot is local-first and sends no QuotaPilot telemetry. It does not store
raw task prompts or full agent transcripts by default. Stored provider account
identity is replaced with a stable provider-scoped SHA-256 correlation digest;
the digest is not a secret. Provider raw observations are sanitized before
persistence, and execution output retained in results is bounded and redacted.

Routing is advisory and heuristic. Profiles may be provisional or stale.
`UNKNOWN` never means safe, zero, or unlimited. Real execution is separately
policy-gated, defaults to interactive confirmation, and may modify the
explicit working directory. Inspect `--dry-run` output before real execution.

No execution audit is currently persisted, so there is no `executions` history
command. Raw tasks and results remain in memory for the process lifetime.

## Requirements

- Python 3.12 or newer.
- Linux is the currently tested operating system.
- `codex` on `PATH` for live capture or real Codex execution.
- Existing Codex authentication for authenticated provider operations.

macOS and Windows have not yet been verified; platform-safe data/config paths
are used, but support is not claimed.

## Installation

The verified local installation flow builds and installs the wheel:

```bash
git clone git@github.com:H1rla/QuotaPilot.git
cd QuotaPilot
uv build
uv tool install dist/quotapilot-0.1.0-py3-none-any.whl
quotapilot --version
```

For development:

```bash
git clone git@github.com:H1rla/QuotaPilot.git
cd QuotaPilot
uv sync --dev
uv run pytest
uv run ruff check .
uv run pyright
```

## Quick start

```bash
quotapilot doctor
quotapilot snapshot capture
quotapilot status
quotapilot budget
quotapilot models
quotapilot route "Fix typo in README"
quotapilot execute "Fix typo in README" --dry-run
```

`status`, `budget`, `models`, routing, and dry-run use the latest persisted
snapshot. `status --refresh` first attempts one live capture and clearly labels
a persisted fallback if capture fails. Real execution performs its own fresh
quota/capability revalidation immediately before each attempt.

## Commands

```text
quotapilot config show [--json]
quotapilot config validate [--json]
quotapilot doctor [--json] [--live]
quotapilot snapshot capture|latest
quotapilot status [--json] [--refresh]
quotapilot budget [--json]
quotapilot models [--json]
quotapilot route TASK [--json]
quotapilot calibrate evaluate [--json]
quotapilot execute TASK --dry-run [--json]
quotapilot execute TASK
quotapilot waybar
```

Expected application failures are concise. Script-relevant exit behavior is:

- `0`: success (Waybar also returns valid error JSON with exit 0),
- `1`: application/provider/data failure,
- `2`: invalid invocation or configuration (Typer usage errors remain `2`),
- denied/cancelled real execution currently returns `1`.

Machine-readable output is versioned where introduced in productization
(`status` and `doctor`) and should be treated as pre-1.0: additive changes are
expected. JSON output contains no ANSI formatting.

## Configuration

The optional canonical config path is resolved by `platformdirs` and is
normally `~/.config/quotapilot/config.yaml` on Linux. Defaults work without a
file. Configuration is strict: unknown keys, coercible numeric strings,
invalid enums, and invalid timezones fail instead of silently reverting.

```yaml
provider:
  default: openai-codex

database:
  # Omit to use the platform data directory.
  path: /home/me/.local/share/quotapilot/quotapilot.db

budget:
  reserve_fraction: 0.10
  timezone: Asia/Tokyo
  stale_after_seconds: 900

routing:
  unknown_quota_pressure: 0.50

execution:
  mode: always_confirm
  max_attempts: 3
  max_same_step_retries: 1
  timeout_seconds: 900

profiles:
  # Omit to use profiles bundled in the installed package.
  directory: /home/me/.config/quotapilot/model_profiles
```

Precedence is:

```text
CLI option > environment > user config > policy defaults > built-in defaults
```

Supported environment overrides:

```text
QUOTAPILOT_CONFIG
QUOTAPILOT_PROVIDER
QUOTAPILOT_DATABASE_PATH
QUOTAPILOT_PROFILE_DIR
QUOTAPILOT_BUDGET_RESERVE_FRACTION
QUOTAPILOT_BUDGET_TIMEZONE
QUOTAPILOT_BUDGET_STALE_AFTER_SECONDS
QUOTAPILOT_ROUTING_UNKNOWN_QUOTA_PRESSURE
QUOTAPILOT_EXECUTION_MODE
QUOTAPILOT_EXECUTION_MAX_ATTEMPTS
QUOTAPILOT_EXECUTION_MAX_SAME_STEP_RETRIES
QUOTAPILOT_EXECUTION_TIMEOUT_SECONDS
```

`quotapilot config show` reports the effective source for each field. It never
enumerates arbitrary environment variables.

## Data locations

- Config: `platformdirs.user_config_dir("quotapilot")/config.yaml`
- Database: `platformdirs.user_data_dir("quotapilot")/quotapilot.db`
- Bundled profiles/calibration: installed package resources
- Persistent logs: none
- Execution audit/task history: none

The paths above have the familiar `~/.config` and `~/.local/share` shape on
Linux, but production code does not hardcode a home directory.

## Waybar

`quotapilot waybar` is a cheap persisted-state read. It never performs live
capture and never executes a model. Add a custom module:

```json
"custom/quotapilot": {
  "exec": "quotapilot waybar",
  "return-type": "json",
  "interval": 60
}
```

Stable classes are `very-under`, `under`, `on-track`, `over`, `critical`,
`unknown`, `stale`, and `error`. A minimal CSS example:

```css
#custom-quotapilot.on-track,
#custom-quotapilot.under,
#custom-quotapilot.very-under { color: #a6e3a1; }
#custom-quotapilot.over { color: #f9e2af; }
#custom-quotapilot.critical,
#custom-quotapilot.error { color: #f38ba8; }
#custom-quotapilot.unknown,
#custom-quotapilot.stale { color: #bac2de; }
```

Even config/database/profile failures produce valid fallback JSON such as
`{"text":"QP ?","tooltip":"QuotaPilot: operational state unavailable","class":"error"}`.

## Architecture

```text
Providers -> Domain -> Persistence
                    -> Budget -> Routing -> Execution planning/policy
                                      ^
                         Capability profiles

CLI / Waybar -> Services -> existing core boundaries
```

Provider-specific RPC and subprocess details remain in adapters. Budget and
routing code do not import Codex or SQLite. Product output does not serialize
raw provider observations or account identity.

Maintainer contracts and durable decisions live under `docs/`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Normal tests are offline and must not
use Codex authentication or execute paid models.

## Roadmap

Next work should observe and calibrate real recommendations without changing
the conservative safety boundaries. Publishing, tags, hosted telemetry, and
autonomous background execution are intentionally out of scope.

## License

MIT. See [LICENSE](LICENSE).
