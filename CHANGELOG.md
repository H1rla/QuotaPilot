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
- PySide6/Qt Quick desktop GUI with seven operational screens, direct service
  integration, async workers, keyboard navigation, and a command palette.
- Explicit UNKNOWN/STALE/error presentation, persisted usage visualization,
  model provenance inspection, and safe settings editing.
- Qt-native System/English/Japanese localization with runtime switching and
  packaged TS/QM resources.
- Privacy-safe Codex connection/authentication and persisted-data status in
  the desktop Overview.
- Focus, hover, selected-row, Japanese font fallback, and 900x600 responsive
  polish for the Phase 8 desktop GUI.

### Security

- Raw account identifiers, tasks, full transcripts, credentials, and provider
  payloads are excluded from default persistence and product observability
  output. The GUI exposes only a normalized authentication availability state.
