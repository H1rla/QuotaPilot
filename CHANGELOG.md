# Changelog

All notable user-visible changes are recorded here. QuotaPilot follows
Semantic Versioning while pre-1.0 interfaces may still evolve.

## [Unreleased]

## [0.1.0] - 2026-09-25

First alpha release. QuotaPilot is experimental and pre-1.0; routing profiles
and coefficients remain provisional.

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
- Textual 8.2.8 TUI foundation launched by `quotapilot tui`, with a
  persisted-first Overview, one eligible safe startup refresh, adaptive
  rail/overlay navigation, focus-aware Arrow/hjkl bindings, localized Ctrl+P
  commands and contextual Help.
- Strict `appearance.tui_theme = system | dark | light`, packaged English and
  Japanese TUI catalogs, and an explicit System-to-Dark fallback.
- Phase 9.2A TUI Route task editor and advisory analysis, real Dry Run and
  controlled Execute plan review with focused approval and cancellation, and
  Models list/detail filtering. Added English/Japanese copy and responsive
  layouts for the three screens.
- TUI Dark and Light palettes now use navy/blue interaction accents and quiet
  neutral surfaces; green is reserved for explicit success.
- Phase 9.2B completes Usage, History, Settings, and Doctor in the TUI. Usage
  and History use bounded persisted snapshots and the existing budget engine;
  execution history remains explicitly unpersisted. Settings stages strict
  changes and saves atomically, with next-launch application. Doctor runs
  offline diagnostics asynchronously. Local filters, details, palette deep
  links, English/Japanese copy, and compact layouts cover the four screens.

### Security

- Raw account identifiers, tasks, full transcripts, credentials, and provider
  payloads are excluded from default persistence and product observability
  output. The GUI exposes only a normalized authentication availability state.
