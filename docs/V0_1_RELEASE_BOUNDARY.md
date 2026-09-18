# QuotaPilot v0.1.0 Release Boundary

Status: Normative release boundary  
Target: First public pre-1.0 release

## 1. Purpose

v0.1.0 is the first coherent local-product release of QuotaPilot.

It is not a claim of production stability. It is an alpha-quality release that proves the full local workflow:

```text
Observe quota
↓
Persist state
↓
Budget usage
↓
Recommend model/effort
↓
Enrich model capabilities
↓
Calibrate routing
↓
Dry-run
↓
Controlled execution
↓
Observe state through CLI / Waybar / GUI
```

## 2. v0.1.0 MUST include

### Core

- Codex provider integration
- coherent usage capture
- quota normalization
- privacy-safe persistence
- budget engine
- quota-pressure calculation
- daily budget
- routing engine
- effort recommendation
- bounded escalation recommendation
- capability enrichment
- model profile provenance/staleness
- calibration scenario replay
- controlled execution
- dry-run
- approval gate
- bounded retry/escalation
- quota/capability revalidation

### CLI / CUI

- `quotapilot status`
- `quotapilot budget`
- `quotapilot models`
- `quotapilot route`
- `quotapilot execute`
- `quotapilot doctor`
- `quotapilot config`
- `quotapilot waybar`
- JSON output for automation surfaces
- OpenCode-inspired compact interaction model where applicable

### GUI

The first GUI release MUST include:

- Overview
- Usage
- Models
- Route
- Execute
- History
- Settings
- Command palette
- keyboard navigation
- dark minimal technical design language
- direct use of QuotaPilot services, not CLI subprocess wrapping

### Release readiness

- README
- LICENSE
- CHANGELOG
- SECURITY
- CONTRIBUTING
- CI
- wheel build/install smoke
- version command
- privacy/security review
- Linux packaging instructions

## 3. v0.1.0 SHOULD include

- Waybar integration docs
- polished error/loading/unknown/stale states
- desktop entry
- application icon
- packaged GUI launcher
- GUI settings editor for common policy values
- usage-history visualization
- provenance/freshness visibility

## 4. v0.1.0 MAY include

- lightweight TUI
- shell completion
- desktop notifications
- execution audit viewer

These are not release blockers unless implementation already exists and only needs polish.

## 5. v0.1.0 MUST NOT imply

- globally optimal routing
- empirically proven model rankings
- production-grade autonomous coding
- multi-provider maturity
- Windows/macOS support unless actually tested
- cloud synchronization
- remote telemetry
- unattended autonomous task execution

## 6. Supported platform statement

Initial support target:

```text
Linux
Python 3.12+
OpenAI Codex CLI
```

Other platforms/providers remain experimental or unsupported until tested.

## 7. Release status language

Use:

```text
alpha
experimental
pre-1.0
```

Do not use:

```text
stable
production-ready
fully autonomous
```

## 8. Final release gate

v0.1.0 may be tagged only when:

```text
Core phases 2–7: COMPLETE
GUI Phase 8: COMPLETE
UI smoke: PASS
CLI smoke: PASS
Waybar smoke: PASS
wheel build/install: PASS
privacy/security review: PASS
README current: PASS
CHANGELOG current: PASS
Git clean: PASS
release tag explicitly approved by user
```

No release/tag/publish action should occur automatically.
