# QuotaPilot Phase 8 — Desktop GUI Contract

Status: Normative implementation contract  
Phase: 8  
Depends on:

- Completed QuotaPilot core through Phase 7
- `docs/UI_DESIGN.md`
- Existing configuration/status/budget/routing/execution services

## 1. Purpose

Phase 8 implements the first desktop GUI for QuotaPilot.

The GUI is a presentation layer over existing QuotaPilot services.

It must not become a second implementation of the core.

Primary stack:

```text
PySide6
Qt Quick / QML
```

## 2. Mandatory screens

Phase 8 MUST implement:

- Overview
- Usage
- Models
- Route
- Execute
- History
- Settings

Phase 8 MUST also implement:

- command palette
- keyboard navigation
- loading states
- UNKNOWN states
- STALE states
- actionable error states

## 3. Architecture

Required dependency direction:

```text
Core Services
    ↓
GUI ViewModels / Controllers
    ↓
QML Views
```

Forbidden:

```text
QML → raw SQLite
QML → OpenAI RPC
QML → duplicated budget math
GUI → shell out to quotapilot CLI for normal operations
```

## 4. GUI package

Suggested:

```text
src/quotapilot/gui/
├── __init__.py
├── app.py
├── viewmodels/
├── controllers/
├── resources/
└── qml/
```

QML files should be componentized.

## 5. Launch surface

Implement:

```bash
quotapilot gui
```

The existing CLI must remain backward-compatible.

GUI launch must not replace existing script behavior unexpectedly.

## 6. Overview

Must expose:

```text
remaining quota
reset
budget state
pressure
today budget
routable models
profile freshness
usage chart
current recommendation if available
```

Information priority follows `UI_DESIGN.md`.

## 7. Usage

Must visualize:

```text
actual usage
expected pace
delta
state
reset
```

Use historical snapshots.

Do not infer missing historical values.

## 8. Models

Must display:

```text
model ID/name
routable
power
cost
latency
effort
profile source
confidence
freshness
```

Detail view exposes evidence/provenance.

## 9. Route

Must provide:

- task input
- analyze action
- TaskProfile summary
- recommendation
- explanation
- escalation
- advanced explicit profile overrides
- Dry Run
- Execute transition

No automatic execution directly from analysis.

## 10. Execute

Must display final ExecutionPlan before approval.

Must include:

```text
model
effort
working directory
quota state
approval status
timeout
max attempts
escalation
warning that files may be modified
```

Real execution uses existing Phase 6 execution service.

## 11. History

Must display available privacy-safe history.

At minimum:

- usage history
- execution metadata if available

Do not invent raw task history.

## 12. Settings

Must edit supported central configuration safely.

Categories:

```text
General
Budget
Routing
Execution
Models & Profiles
Integration
Appearance
```

Invalid changes must be rejected with clear feedback.

## 13. Command palette

`Ctrl+P` is mandatory.

It must navigate and trigger safe non-destructive actions.

Destructive/real execution must not occur directly from palette without normal execution approval flow.

## 14. Keyboard

At minimum:

```text
Ctrl+P command palette
Ctrl+R refresh
Ctrl+D details
Ctrl+, settings
Esc back/cancel
Enter select/confirm
```

All primary flows should be possible without mouse.

## 15. Async

Provider refresh, DB operations, routing, and execution must not freeze Qt's main thread.

Use appropriate async worker/Qt integration.

## 16. Styling

Implement design tokens from `UI_DESIGN.md`.

Use:

```text
dark minimal technical design
limited semantic color
subtle borders
compact spacing
restrained radius
```

No generic card-heavy SaaS dashboard.

## 17. Charts

Charts must be minimal.

Usage visualization should prioritize actual vs expected.

Do not add decorative charts without operational value.

## 18. Privacy

GUI must not display:

- raw account ID
- credentials
- raw provider payloads
- task history not already explicitly stored

Execution outputs must remain bounded/redacted according to Phase 6.

## 19. Error behavior

Normal errors are shown inline.

No raw traceback in normal GUI.

Provide actions such as:

```text
Retry
Open Doctor
Use persisted state
Open Settings
```

where appropriate.

## 20. Packaging

GUI runtime dependencies/assets must be packaged correctly.

Wheel/install smoke must verify:

```text
quotapilot gui
```

can locate QML/resources.

Linux desktop entry/icon MAY be added.

## 21. Tests

At minimum cover:

- ViewModel state mapping
- UNKNOWN
- STALE
- provider unavailable
- no snapshot
- route result
- no-route
- execute dry-run
- approval-required plan
- invalid settings
- command palette actions
- privacy-sensitive data absence

QML smoke tests should be used where practical.

## 22. Non-goals

Phase 8 does NOT implement:

- cloud dashboard
- mobile app
- remote sync
- new routing math
- new quota math
- autonomous execution
- semantic LLM evaluator

## 23. Completion criteria

Phase 8 is complete when:

1. GUI launches from installed package.
2. All seven mandatory screens work.
3. Overview matches design hierarchy.
4. Command palette works.
5. Keyboard navigation works.
6. Core services are called directly.
7. GUI does not duplicate business logic.
8. Usage history is visualized correctly.
9. Model provenance/freshness is inspectable.
10. Route explanation is visible.
11. Execute confirmation uses Phase 6.
12. Settings safely update supported config.
13. UNKNOWN/STALE/error states are implemented.
14. Async operations do not freeze UI.
15. Privacy review passes.
16. GUI packaging smoke passes.
17. Existing CLI tests remain green.
18. No automatic release is performed.

## 24. v0.1.0 relationship

After Phase 8 passes its acceptance gate, QuotaPilot may enter final v0.1.0 release-candidate verification according to `docs/V0_1_RELEASE_BOUNDARY.md`.

Tagging/publishing still requires explicit user approval.
