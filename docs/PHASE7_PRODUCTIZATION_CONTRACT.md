# QuotaPilot Phase 7 — Productization, Observability & Release Readiness Contract

Status: Implemented normative contract
Phase: 7
Depends on:

- Phase 2 — Provider boundary
- Phase 3 / 3.1 — Persistence boundary
- Phase 4 / 4.1 — Budget Engine
- Phase 5 — Quota-aware Routing Engine
- Phase 5.5 — Capability Metadata & Routing Calibration
- Phase 6 — Controlled Execution & Agent Integration

Phase 7 turns the working QuotaPilot core into a coherent, configurable, observable, distributable user-facing tool.

---

## 1. Purpose

QuotaPilot already supports the core pipeline:

```text
Provider quota/capabilities
        ↓
UsageSnapshot
        ↓
Persistence
        ↓
BudgetReport
        ↓
TaskProfile
        ↓
RoutingRecommendation
        ↓
Capability Enrichment
        ↓
Controlled ExecutionPlan
        ↓
ExecutionResult
```

Phase 7 focuses on productization rather than introducing another decision engine.

The goals are:

- configuration usable by real users,
- observability of quota/routing/execution state,
- Waybar integration,
- terminal user experience,
- safe execution audit inspection,
- packaging and installation,
- release-quality documentation,
- stable machine-readable interfaces,
- diagnostics,
- release readiness.

Phase 7 MUST NOT redesign proven Phase 2–6 algorithms without a concrete defect.

---

## 2. Scope

Phase 7 MUST implement or complete:

- user configuration loading,
- configuration precedence,
- strict configuration validation,
- useful `status` experience,
- Waybar-compatible output,
- execution audit visibility if audit data exists,
- model/profile inspection UX,
- doctor/diagnostics improvements,
- stable JSON output contracts where needed,
- packaging verification,
- installation documentation,
- operational README,
- release metadata,
- changelog/release preparation,
- privacy/security documentation,
- end-to-end smoke tests.

Phase 7 SHOULD consider:

- a lightweight TUI if it materially improves daily use,
- shell completion documentation,
- example configuration,
- systemd user timer/service only if justified,
- local notification hooks only if simple and opt-in.

Phase 7 MUST NOT introduce:

- cloud telemetry by default,
- hosted accounts,
- remote control plane,
- autonomous background model execution,
- opaque policy learning,
- browser scraping,
- arbitrary plugin execution.

---

## 3. Productization principle

Phase 7 must preserve:

```text
Core logic
    ↓
Services
    ↓
CLI / Waybar / TUI
```

UI layers consume existing domain/service contracts.

They MUST NOT reimplement:

- quota normalization,
- budget mathematics,
- routing scores,
- capability enrichment,
- execution policy.

---

## 4. Desired user workflows

At the end of Phase 7, a user should be able to perform these workflows naturally.

```bash
quotapilot status
quotapilot budget
quotapilot route "Investigate this repository-wide bug"
quotapilot models
quotapilot execute "Fix typo in README" --dry-run
quotapilot execute "Fix typo in README"
quotapilot doctor
quotapilot waybar
```

The exact command set MAY differ if equivalent interfaces already exist.

Do not create duplicate commands unnecessarily.

---

## 5. Configuration file

Canonical user configuration location:

```text
~/.config/quotapilot/config.yaml
```

resolved through `platformdirs`.

Do not hardcode a home directory.

A user MUST be able to run QuotaPilot with built-in defaults when no config file exists.

---

## 6. Configuration domains

Configuration SHOULD be grouped by responsibility.

Conceptual example:

```yaml
provider:
  default: openai-codex

budget:
  reserve_fraction: 0.10
  timezone: Asia/Tokyo
  stale_after_seconds: 900

routing:
  policy: balanced
  unknown_quota_pressure: 0.50

execution:
  mode: always_confirm
  max_attempts: 3
  max_same_step_retries: 1
  timeout_seconds: 1800

profiles:
  search_paths: []

ui:
  output: human
  unicode: true

waybar:
  enabled: true
```

The exact schema must reuse existing Phase 2–6 policy models where possible.

Do not duplicate policy schemas.

---

## 7. Configuration precedence

Configuration precedence MUST be deterministic and documented.

Recommended:

```text
1. CLI option
2. environment variable
3. user config file
4. policy/profile defaults
5. built-in defaults
```

Lower-precedence sources must never silently override higher-precedence sources.

---

## 8. Strict configuration

Configuration must fail early on malformed policy.

Reject:

- unknown keys,
- misspelled fields,
- invalid enum values,
- invalid numeric ranges,
- booleans passed as numbers,
- malformed timezones,
- invalid paths where validation is possible.

Do not silently fall back to defaults after a typo.

---

## 9. Environment variables

Environment variables MAY override selected settings.

Use a consistent namespace:

```text
QUOTAPILOT_...
```

Document supported variables.

Do not allow environment variables to inject arbitrary Python code, shell fragments, or executable hooks.

Sensitive environment values must never be printed by diagnostics.

---

## 10. Configuration inspection

Provide a safe way to inspect effective configuration.

Possible command:

```bash
quotapilot config show
```

Output should indicate source where practical:

```text
reserve_fraction = 0.10  [user-config]
execution.mode = always_confirm  [default]
```

Do not print secrets.

---

## 11. Configuration validation

A command such as:

```bash
quotapilot config validate
```

SHOULD be provided if useful.

It should validate configuration without executing providers or agents.

---

## 12. Status command

`quotapilot status` should become the main compact operational overview.

It SHOULD show:

- provider/product,
- data source,
- quota pools,
- remaining fractions,
- reset times,
- snapshot age,
- budget state,
- effective pressure,
- binding pool,
- today's suggested budget,
- warnings,
- profile freshness summary.

Do not expose raw account IDs.

---

## 13. Status JSON

Support:

```bash
quotapilot status --json
```

Machine-readable output should remain typed and privacy-safe.

It must distinguish:

```text
null
0
unknown
stale
```

correctly.

---

## 14. Waybar output

Implement:

```bash
quotapilot waybar
```

with Waybar-compatible JSON.

Minimum shape:

```json
{
  "text": "QP 35%",
  "tooltip": "Weekly remaining: 35%\nState: OVER",
  "class": "over"
}
```

The implementation must derive values from the same status/budget services used by the CLI.

No duplicate budget logic.

---

## 15. Waybar classes

Use stable classes suitable for CSS.

Suggested:

```text
very-under
under
on-track
over
critical
unknown
stale
error
```

---

## 16. Waybar failure behavior

Waybar output must degrade gracefully.

Provider/database/config failure should still produce valid JSON.

Example:

```json
{
  "text": "QP ?",
  "tooltip": "QuotaPilot: provider unavailable",
  "class": "error"
}
```

Do not print a traceback to Waybar stdout.

---

## 17. Waybar polling

Phase 7 SHOULD NOT add a heavy permanent daemon solely for Waybar unless measurements justify it.

Prefer:

```text
Waybar interval
→ lightweight quotapilot waybar invocation
```

Use persisted state where appropriate.

Waybar MUST never trigger paid model execution.

---

## 18. TUI

A TUI is optional.

If implemented, possible views include:

```text
Overview
Quota pools
Budget
Models
Profiles
Execution history
Diagnostics
```

Do not create a second business-logic layer.

A polished CLI + Waybar is sufficient for Phase 7 completion.

---

## 19. Execution audit visibility

If Phase 6 exposes audit metadata, provide safe inspection.

Possible commands:

```bash
quotapilot executions list
quotapilot executions show <id>
```

Display metadata such as:

- timestamp,
- model,
- effort,
- status,
- failure class,
- attempts,
- quota pressure,
- task hash.

Do not show raw task content by default.

---

## 20. No automatic task history

Phase 7 MUST NOT introduce automatic persistence of:

- user prompts,
- source code,
- full agent transcripts.

Execution observability remains metadata-focused.

---

## 21. Doctor command

Strengthen:

```bash
quotapilot doctor
```

Diagnostics SHOULD cover:

- runtime compatibility,
- database path/writability,
- schema version,
- config validity,
- Codex executable presence,
- Codex CLI version,
- safe authentication availability check,
- app-server availability,
- model profile loading,
- profile freshness,
- routable model count,
- provider capture health,
- Waybar output generation,
- execution adapter availability.

Do not expose secrets.

---

## 22. Doctor result model

Use structured checks:

```text
PASS
WARN
FAIL
SKIP
```

Each check should have:

```text
name
status
short explanation
optional remediation
```

JSON output is desirable.

---

## 23. Remediation messages

Doctor failures should be actionable.

Example:

```text
FAIL: Codex CLI not found
Install/configure Codex CLI and ensure `codex` is in PATH.
```

Avoid generic errors.

---

## 24. Logging

Standardize application logging.

Default:

```text
WARNING
```

Debug mode MAY enable:

```text
DEBUG
```

Logs MUST NOT contain:

- credentials,
- raw task text by default,
- account IDs,
- raw provider payloads,
- environment secrets.

---

## 25. Debug mode

A command-level debug option MAY exist:

```bash
quotapilot --debug ...
```

Debug mode is not permission to print secrets.

---

## 26. Error UX

Expected application failures should produce concise messages rather than raw tracebacks.

Examples:

- no snapshot available,
- invalid config,
- provider unavailable,
- no routable model,
- stale profile,
- execution denied.

Unexpected tracebacks MAY appear in explicit debug mode.

---

## 27. Exit codes

CLI commands SHOULD use stable exit-code semantics.

Conceptual mapping:

```text
0 = success
1 = application failure
2 = invalid invocation/config
3 = provider unavailable
4 = execution denied/cancelled
```

Document any non-zero codes that scripts may rely upon.

---

## 28. Output modes

Human and JSON output must remain clearly separated.

Do not mix terminal formatting into JSON.

JSON stdout should remain valid JSON.

Logs/errors should use stderr where appropriate.

---

## 29. Stable JSON philosophy

Phase 7 should identify machine-facing JSON surfaces, likely:

- status,
- budget,
- route,
- models,
- execution dry-run,
- doctor,
- waybar.

Document compatibility expectations.

Do not promise premature permanent API stability.

---

## 30. JSON schema versioning

For important automation surfaces, consider:

```text
schema_version
```

in top-level output.

Do not add heavy versioning where it provides no value.

---

## 31. Packaging

Verify clean Python packaging.

Expected:

```bash
uv build
```

The wheel/sdist MUST include required runtime assets such as:

- model profiles,
- calibration assets if required at runtime,
- package metadata.

It MUST NOT include:

- `.git`,
- `.venv`,
- caches,
- private fixtures,
- local databases,
- user config.

---

## 32. Runtime resource loading

Bundled profiles/resources must load correctly from installed wheels.

Do not assume execution from repository root.

Use package-safe resource mechanisms such as `importlib.resources` where appropriate.

---

## 33. Installation

README must document tested installation workflows.

Potential options:

```bash
uv tool install ...
pipx install ...
pip install ...
```

Only document methods that have been verified.

---

## 34. Development setup

Contributor setup should be separate from end-user installation.

Example:

```bash
git clone ...
cd QuotaPilot
uv sync
uv run pytest
```

---

## 35. Versioning

Confirm a project versioning strategy.

Semantic Versioning is recommended.

A pre-1.0 release such as:

```text
0.1.0
```

is appropriate if supported by actual release readiness.

Do not imply `1.0` stability prematurely.

---

## 36. Single version source

Version must have a clear source of truth across:

- package metadata,
- CLI,
- release artifacts.

Avoid inconsistent duplicate version strings.

---

## 37. Version CLI

Support:

```bash
quotapilot --version
```

It must report the packaged version.

---

## 38. Changelog

Create or maintain:

```text
CHANGELOG.md
```

Keep it concise and user-oriented.

Include major completed capabilities rather than a raw commit dump.

---

## 39. README

The README should be user-oriented.

Recommended sections:

```text
What is QuotaPilot?
Why it exists
Current status
Key features
Safety model
Installation
Quick start
Usage examples
Configuration
Waybar integration
Architecture overview
Development
Roadmap
License
```

Detailed phase contracts stay under `docs/`.

---

## 40. Quick start

A new user should quickly understand:

```bash
quotapilot doctor
quotapilot status
quotapilot budget
quotapilot route "Fix typo in README"
quotapilot execute "Fix typo in README" --dry-run
```

---

## 41. Safety documentation

Document clearly:

- routing is heuristic,
- model profiles may be provisional,
- execution is policy-gated,
- default real execution requires confirmation,
- quota calculations depend on provider-reported data,
- unknown/stale data remains visible.

---

## 42. Privacy documentation

Document:

- local-first design,
- telemetry disabled by default,
- no raw task persistence by default,
- pseudonymized account identity,
- bounded/redacted execution output,
- local data/config paths.

Do not claim more than implementation supports.

---

## 43. Data locations

Document platform-resolved locations for:

- configuration,
- SQLite database,
- logs if persistent logs exist,
- profile overrides if supported.

Do not hardcode platform assumptions into production logic.

---

## 44. User profile overrides

Phase 7 MAY support local model-profile search paths.

If implemented:

- precedence must be explicit,
- conflicts deterministic,
- invalid override visible,
- no remote auto-download.

---

## 45. Config initialization

Optional:

```bash
quotapilot config init
```

It must not overwrite existing config without explicit approval.

---

## 46. Shell completion

Shell completion documentation is optional.

Do not make it a release blocker.

---

## 47. Waybar documentation

Provide a tested Waybar snippet, conceptually:

```json
"custom/quotapilot": {
  "exec": "quotapilot waybar",
  "return-type": "json",
  "interval": 60
}
```

Also provide CSS examples.

---

## 48. Waybar privacy

Tooltip must not expose:

- account IDs,
- task text,
- unnecessary execution details.

Quota/budget/profile warnings are acceptable.

---

## 49. Notifications

Notifications are optional and must be local and opt-in.

Possible events:

- CRITICAL quota pressure,
- stale profile,
- execution attention required.

Do not create spammy periodic notifications.

---

## 50. Background operation

A permanent daemon is not required.

Prefer on-demand CLI calls and persisted state.

Any background refresh must be justified, documented, and opt-in.

---

## 51. Release security review

Before release inspect for:

- credentials,
- API keys,
- private fixtures,
- raw telemetry,
- local DB files,
- task text,
- logs/debug dumps,
- unsafe subprocess calls,
- shell interpolation,
- unsafe YAML loading.

Mandatory.

---

## 52. Dependency review

Review runtime dependencies.

Remove unused dependencies.

Separate runtime and development dependencies where practical.

Avoid large UI dependencies unless actually used.

---

## 53. License

Ensure a project license exists before public release.

If code was directly copied or substantially adapted from third-party OSS:

- verify license compatibility,
- preserve required notices,
- add attribution/NOTICE where necessary.

---

## 54. Third-party attribution

Distinguish:

```text
inspiration
```

from:

```text
copied/adapted source
```

Follow actual licenses.

---

## 55. GitHub repository polish

Recommended files:

```text
README.md
LICENSE
CHANGELOG.md
SECURITY.md
CONTRIBUTING.md
```

Optional:

```text
.github/ISSUE_TEMPLATE/
.github/PULL_REQUEST_TEMPLATE.md
```

Avoid misleading boilerplate.

---

## 56. SECURITY.md

Explain how to report:

- credential leakage,
- unsafe command execution,
- privacy bugs,
- quota/account-data leakage.

Do not promise response SLAs that cannot be maintained.

---

## 57. CONTRIBUTING.md

Contributor docs SHOULD include:

- environment setup,
- architecture boundaries,
- test commands,
- contract/decision process,
- privacy rules,
- fixture sanitization,
- model-profile update process.

---

## 58. CI

Required CI checks:

```text
pytest
ruff
pyright
build
```

Normal CI MUST NOT require:

- authenticated Codex,
- real model execution,
- live account access.

Live integration remains opt-in/manual.

---

## 59. Build smoke test

Release verification should test:

```text
build wheel
install wheel in clean environment
run quotapilot --help
run quotapilot --version
run non-network smoke command
```

This catches missing packaged assets.

---

## 60. Offline behavior

QuotaPilot should still provide useful functionality when live provider access is unavailable.

Examples:

- config validation,
- profile inspection,
- persisted snapshot status,
- calibration evaluation,
- dry-run limitations where enough stored data exists.

---

## 61. Release checklist

Create a release checklist containing at minimum:

```text
tests pass
ruff pass
pyright pass
build succeeds
wheel smoke passes
privacy scan passes
security review passes
README current
CHANGELOG current
version updated
Git clean
tag ready
```

Publishing remains explicit.

---

## 62. Release tagging

A release MAY use a tag such as:

```text
v0.1.0
```

Do not tag until release gates pass.

---

## 63. No automatic publishing

Do not automatically publish to PyPI or create a GitHub release without explicit user instruction.

Phase 7 prepares release readiness.

---

## 64. Performance

Measure obvious user-facing commands.

Ensure:

- config loading is fast,
- persisted status is responsive,
- Waybar invocation is practical,
- profile loading is not unnecessarily repeated.

Avoid premature micro-optimization.

---

## 65. Caching

Any new cache requires explicit invalidation semantics.

Do not add hidden caches just for speed.

---

## 66. UX consistency

Use consistent terms:

```text
quota
remaining
budget
pressure
model
effort
profile
execution
```

Avoid ambiguous synonyms.

---

## 67. Color and terminal formatting

Rich output is acceptable.

Requirements:

- readable without color,
- JSON has no ANSI escape codes,
- `NO_COLOR` SHOULD be respected where practical,
- semantics must not rely on color alone.

---

## 68. Accessibility

Always pair color with text labels such as:

```text
CRITICAL
UNKNOWN
STALE
```

---

## 69. Compact mode

Optional:

```bash
quotapilot status --compact
```

Do not use compact human output as a replacement for stable JSON.

---

## 70. Unknown data UX

Productization must preserve conservative semantics.

UNKNOWN remains UNKNOWN.

Never render unknown as:

```text
0
safe
unlimited
```

Stale values remain visibly stale.

---

## 71. Failure fallback

Live provider failure must not erase valid persisted information.

Where appropriate:

```text
live unavailable
→ show latest persisted snapshot
→ label source and staleness
```

Never present fallback data as live.

---

## 72. End-to-end smoke scenarios

Phase 7 MUST include or document offline smoke coverage:

```text
load config
load bundled profiles
open temp DB
load snapshot
budget
route
execution dry-run
```

Optional live smoke:

```text
capture
persist
budget
enrich
route
dry-run
```

Live smoke MUST NOT perform paid execution automatically.

---

## 73. Real execution smoke

Real execution remains separately gated by the Phase 6 execution integration flag.

It is not required for normal CI.

---

## 74. Compatibility

Document supported Python version from `pyproject.toml`.

Operating-system support must be described conservatively.

Do not claim macOS/Windows support unless tested.

---

## 75. Persistence compatibility

Existing databases must continue to work.

Phase 7 must not reset user history.

Persistence schema changes require proper migration/version handling.

---

## 76. Configuration evolution

Prefer strict current schema plus explicit future migration.

Do not use permissive unknown-field behavior merely for hypothetical forward compatibility.

---

## 77. Documentation boundary

Phase contracts are maintainer specifications.

README/user docs should describe features rather than phase numbers.

---

## 78. Naming

Use:

```text
QuotaPilot
```

for product name and:

```text
quotapilot
```

for CLI.

Do not introduce alternate names without deliberate decision.

---

## 79. Release status

Before stable release use accurate language such as:

```text
alpha
experimental
pre-1.0
```

Do not imply production guarantees not supported by evidence.

---

## 80. Calibration warning

User documentation must state that routing/profile coefficients are heuristic and may be provisional.

Calibration regression tests do not prove global optimality.

---

## 81. Execution warning

Document that real agent execution may modify the working directory.

Dry-run and confirmation exist for this reason.

---

## 82. Data backup

Automatic backup is not required.

Documentation MAY state where the local SQLite database is stored for users who want backups.

---

## 83. Doctor privacy test

Test `quotapilot doctor` with fake secrets/environment values and verify they are not printed.

This is a release gate.

---

## 84. JSON privacy test

Machine-readable outputs must be tested for:

- raw account IDs,
- credentials,
- raw provider payloads,
- unintended task text.

---

## 85. Waybar test matrix

Test Waybar output for:

- ON_TRACK,
- CRITICAL,
- UNKNOWN,
- stale,
- provider failure.

Every case must emit syntactically valid JSON.

---

## 86. Config test matrix

Test:

- no config,
- valid config,
- malformed YAML,
- unknown key,
- invalid enum,
- env override,
- CLI override,
- precedence,
- invalid timezone,
- invalid path.

---

## 87. Packaging test matrix

Test:

- source checkout,
- editable install if supported,
- built wheel,
- bundled profile loading,
- runtime calibration assets if needed,
- CLI entry point,
- version output.

---

## 88. Documentation smoke

Commands shown in README quick-start should be tested or manually verified.

Avoid stale examples.

---

## 89. Phase 7 non-goals

Phase 7 does NOT include:

- mobile app,
- hosted dashboard,
- cloud synchronization,
- remote account service,
- shared team state,
- autonomous background coding,
- generic plugin marketplace.

---

## 90. Acceptance criteria

Phase 7 is complete when:

1. Strict config loader exists.
2. Config precedence is deterministic.
3. Effective config can be inspected safely.
4. `status` provides a coherent overview.
5. `status --json` is privacy-safe.
6. Waybar output exists and is valid JSON.
7. Waybar error degradation works.
8. Doctor provides actionable diagnostics.
9. Doctor does not leak secrets.
10. Model/profile observability is coherent.
11. Execution observability is available where applicable.
12. Human and JSON output are separated cleanly.
13. Package builds successfully.
14. Wheel installation smoke succeeds.
15. Required runtime assets are included.
16. `--version` works.
17. README is user-oriented and current.
18. Installation instructions are verified.
19. Configuration is documented.
20. Waybar setup is documented.
21. Privacy model is documented.
22. Execution safety is documented.
23. CHANGELOG exists and is current.
24. LICENSE exists.
25. SECURITY.md exists.
26. CONTRIBUTING.md exists.
27. CI runs pytest, Ruff, Pyright, and build.
28. Normal CI performs no real agent execution.
29. Offline end-to-end smoke passes.
30. Live opt-in capture→budget→route→dry-run path passes where available.
31. Privacy scan passes.
32. Security review passes.
33. Git working tree is clean after commit/push.
34. No automatic publishing occurs without explicit user request.

---

## 91. Completion boundary

At the end of Phase 7, QuotaPilot should be usable as a coherent local product:

```text
Install
  ↓
Configure
  ↓
Doctor
  ↓
Observe quota
  ↓
Understand budget
  ↓
Get routing recommendation
  ↓
Inspect model/profile provenance
  ↓
Dry-run
  ↓
Controlled execution
  ↓
Inspect operational state
```

The core remains local-first, explainable, quota-aware, privacy-conscious, and policy-gated.

---

## 92. Post-Phase-7 possibilities

Potential later work may include:

- empirical calibration from opt-in feedback,
- additional providers,
- TUI refinement,
- desktop notifications,
- richer execution verification,
- remote signed profile distribution,
- release automation.

These require separate contracts and are not implied by Phase 7 completion.
