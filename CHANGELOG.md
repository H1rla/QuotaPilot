# Changelog

All notable user-visible changes are recorded here. QuotaPilot follows
Semantic Versioning while pre-1.0 interfaces may still evolve.

## [Unreleased]

### Added

- Atomic Codex quota/capability capture and sanitized fixtures.
- Privacy-safe SQLite snapshot history.
- Conservative budget pacing, reserve, daily allocation, and pressure.
- Explainable quota-aware model/effort routing and capability profiles.
- Deterministic routing calibration scenarios.
- Policy-gated dry-run and controlled Codex execution.
- Strict layered user configuration.
- Privacy-safe status, Waybar JSON, and structured doctor diagnostics.
- Wheel/sdist build and offline release smoke coverage.

### Security

- Raw account identifiers, tasks, full transcripts, credentials, and provider
  authentication state are excluded from default persistence and product
  observability output.
