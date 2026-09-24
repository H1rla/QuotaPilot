# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design, phase contracts, and decision log before continuing.

## Current state

- Date: 2026-09-25
- Last agent: Codex
- Current phase: **v0.1.0 local release gate passed; final user approval pending**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing boundary: **COMPLETE**
- Phase 5.5 enrichment/calibration boundary: **COMPLETE**
- Phase 6 controlled execution boundary: **COMPLETE**
- Phase 7 productization/release-readiness boundary: **COMPLETE**
- Phase 8 PySide6/QML GUI boundary: **COMPLETE**
- Phase 8.1 localization/provider-status/polish boundary: **COMPLETE**
- GUI RC scroll/alignment/information-hierarchy polish: **COMPLETE**
- Phase 9 interactive TUI design/implementation contract: **APPROVED**
- Phase 9.1 TUI Foundation: **COMPLETE**
- Phase 9.2A Route/Execute/Models: **COMPLETE**
- TUI navy/blue identity polish: **COMPLETE**
- Phase 9.2B Usage/History/Settings/Doctor: **COMPLETE**
- Release readiness: **local release gate passed; final user approval pending**
- Publishing/tag/GitHub release: **NOT PERFORMED**

The implemented Phase 7 contract is
`docs/PHASE7_PRODUCTIZATION_CONTRACT.md`. The reusable pre-publication gate is
`docs/RELEASE_CHECKLIST.md`.

The implemented Phase 8 contract is `docs/PHASE8_GUI_CONTRACT.md`; its visual
authority is `docs/UI_DESIGN.md` plus the local `quotapilot-ui` Skill.

The approved Phase 9 UX authority is `docs/CUI_DESIGN.md`; its implementation
contract is `docs/PHASE9_TUI_CONTRACT.md`. The user separately authorized
Phase 9.2A and 9.2B; release work remains separate.

## Phase 7 implementation

### Strict central configuration

- `src/quotapilot/config/` loads optional safe YAML from the platformdirs user
  config path and validates one strict `AppConfig` (`extra="forbid"`).
- Existing `BudgetConfig`, `RoutingPolicy`, and `ExecutionPolicy` are embedded;
  no duplicate policy schema was introduced.
- Precedence is CLI > selected `QUOTAPILOT_*` environment variables > user
  config > policy defaults > built-ins. String/enum conversion happens
  explicitly at the loader boundary before strict validation.
- `quotapilot config show [--json]` reports effective field sources;
  `config validate [--json]` performs no provider or execution access.
- Budget, route, models, snapshot, and execute commands now consume central
  database/provider/profile/policy settings while preserving their CLI
  overrides.

### Status and Waybar

- `StatusService` composes repository snapshots, the existing Budget Engine,
  and capability enrichment into strict privacy-safe status models. It does
  not expose account IDs, plan labels, raw observations, or raw capability
  metadata.
- `quotapilot status [--json]` defaults to persisted state. `--refresh`
  performs one explicit coherent Codex capture/store; on failure it retains and
  labels a `persisted_fallback` rather than presenting cached data as live.
- `quotapilot waybar` is persisted-only and produced in about 0.30 seconds in
  a clean no-snapshot smoke. Stable classes are `very-under`, `under`,
  `on-track`, `over`, `critical`, `unknown`, `stale`, and `error`.
- Waybar never contacts the provider or execution adapter, and every failure
  path returns one generic valid JSON object with exit code 0.

### Doctor and output UX

- `quotapilot doctor [--json]` returns PASS/WARN/FAIL/SKIP checks for runtime,
  strict config, database/schema, Codex executable/version/auth/app-server,
  model profiles/freshness, routable models, provider capture, Waybar, and the
  execution adapter.
- Default doctor does not capture provider data; `--live` is explicit.
  Authentication command output is discarded, and raw exceptions/environment
  values are never reflected in diagnostics.
- Root `--version` reads installed package metadata (`0.1.0`), while the
  existing `version` command remains compatible. `--debug` enables standard
  stderr logging; application JSON remains plain JSON without ANSI markup.
- No execution-history command was added because Phase 6 persists no audit.

### Packaging and repository readiness

- `uv build` creates a wheel and sdist. The wheel contains the bundled exact-ID
  model profiles, calibration scenarios, package metadata, and MIT license; it
  contains no fixtures, DB, config, caches, venv, or Git data.
- A clean temporary venv installed the wheel and passed `--version`, `--help`,
  config validation, bundled profile loading, and calibration replay.
- An isolated `uv tool install` of the wheel also passed `quotapilot --version`.
- CI now runs pytest, Ruff, Pyright, CLI/calibration smoke, build, isolated
  wheel installation, and installed-resource smoke. It sets neither live
  integration gate nor execution integration gate.
- README is user-facing and documents verified wheel installation, quick
  start, strict config/environment overrides, data locations, Waybar, safety,
  privacy, compatibility, and architecture.
- `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and the release
  checklist are present. No third-party copied/adapted source requiring a
  NOTICE was found; dependencies are not vendored.

## Phase 8 implementation

### Desktop architecture and async boundary

- `src/quotapilot/gui/` is a PySide6/Qt Quick presentation layer over the
  existing services. `dependencies.py` is the composition root; QML never
  reads SQLite, calls provider RPC, performs budget/routing math, or invokes
  `quotapilot` as a subprocess.
- Provider refresh, SQLite history, routing, execution planning, and controlled
  execution run through `AsyncRunner` workers on `QThreadPool`, each with its
  own asyncio loop. Qt's main thread only maps and renders returned state.
- `quotapilot gui` is registered through a lazy CLI import. Existing non-GUI
  commands do not import PySide6.

### Screens and interaction

- Seven QML screens are present: Overview, Usage, Models, Route, Execute,
  History, and Settings. Shared components and all color/spacing/radius/type/
  motion values live under `gui/qml/components/` and `gui/qml/Tokens.js`.
- Overview uses one technical workspace rather than KPI cards. UNKNOWN and
  STALE remain explicit; green is limited to interaction/selection/actual
  usage while warning/error states keep semantic colors and text.
- Usage/History use only persisted snapshots and do not interpolate missing
  points. Models exposes exact IDs, routability, profile freshness,
  provenance, confidence, evidence, and supported effort order.
- Route analysis never executes. Execute separately builds and displays the
  complete Phase 6 plan, directory-modification warning, dry-run action, and
  explicit approval action. A changed escalation is never implicitly approved.
- `Ctrl+P`, `Ctrl+R`, `Ctrl+D`, `Ctrl+,`, `Esc`, Enter, and palette arrow
  navigation are wired. The palette contains navigation and safe actions only.
- Settings searches all required categories and saves common strict policy
  values atomically through `save_user_config`; changes apply on next launch.
  No provider credential or arbitrary environment value is written.

### Packaging and tests

- PySide6 is a runtime dependency. QML/JS assets are normal package data and
  were verified inside the built wheel. An isolated wheel installation passed
  `quotapilot --version`, `quotapilot gui --smoke-test`, and resource lookup.
- `tests/unit/test_gui_phase8.py` covers mappings, UNKNOWN, STALE, provider
  unavailable, no snapshot/no route, routing, dry-run, approval-required plans,
  invalid settings, command actions, privacy, and offscreen QML loading.
- Full-engine smoke exposed a QML `state` role collision with QQuickItem; roles
  are now named `statusValue`/`statusText`, recorded in `lessons.md`.

## Phase 8.1 implementation

### Localization

- `appearance.language` is a strict `system | en | ja` setting in the normal
  configuration model. Resolution is explicit preference, then system locale,
  then English; unknown locales safely fall back to English.
- QML source strings use English `qsTranslate("Global", ...)` entries. The
  packaged `gui/i18n/quotapilot_{en,ja}.{ts,qm}` catalogs are loaded with
  `QTranslator`; Japanese is concise developer-tool language and identifiers,
  paths, config keys, model/provider IDs, and commands remain canonical.
- Numeric routing explanations are split into a stable source template plus
  arguments by the GUI mapper and formatted through `qml/I18n.js`; unknown
  future core explanations safely fall back to their canonical source text.
- `TranslationManager` owns the translator and calls
  `QQmlApplicationEngine.retranslate()` after an atomic Settings save. Language
  changes therefore apply without restarting; other settings retain the
  Phase 8 next-launch behavior.

### Provider status and polish

- `OpenAICodexProvider.inspect_status()` performs one privacy-safe
  `account/read`. Presence of the normalized account object means
  authenticated; `requiresOpenaiAuth` is a provider requirement, not proof of
  missing authentication. No account identity, plan label, token, or raw
  response crosses the provider boundary.
- `ProviderStatusService` combines inspection with the existing persisted
  status report. The Overview ViewModel exposes Connected, Unavailable, Not
  authenticated, Unknown, Fresh/Stale, and persisted-fallback states without
  collapsing unknown into disconnected.
- Overview keeps provider status secondary to quota/budget information. The
  area stacks at compact width; navigation/model/palette hover states,
  separators, empty/error states, Japanese font fallback, and dynamic UNKNOWN
  value translation were polished without changing semantic state colors.

## GUI release-candidate polish

- All five document-style scrollable screens now use one `PageScrollView`.
  Its explicit content geometry includes the real top and bottom page gutters;
  the previous single-child auto sizing omitted the child's positive `y`
  offset and made the final 24 pixels reachable only during overshoot.
- History headers and rows use the same parent-owned Actual/Expected/State
  widths and the same Layout constraints. English and Japanese measurements
  now have identical header/value x coordinates and widths.
- Default density was reduced without removing data: Overview raises the
  recommendation/Route action ahead of the chart, keeps provider
  connection/freshness compact, and puts diagnostic metrics behind `Ctrl+D`;
  Models hides its provenance panel until details are enabled; Route leads with
  recommendation plus a three-field summary and progressively discloses the
  full profile/explanation; Settings keeps policy controls and appearance in
  view while technical paths/integration metadata remain searchable or
  available in details mode.
- UNKNOWN/STALE text, provider status, quota state, routing explanation,
  escalation, execution directory/approval/timeout/attempt limits, focus and
  keyboard navigation, and semantic status colors remain present.
- `tests/unit/test_gui_qml_layout.py` exercises the common scroll geometry at
  both supported sizes and verifies History column alignment with real English
  and Japanese Qt translations.

## Phase 9 TUI design

- Design only: no TUI package, dependency, CLI command, configuration field, or
  production behavior was implemented.
- Created `docs/CUI_DESIGN.md` and `docs/PHASE9_TUI_CONTRACT.md`; appended the
  resulting architecture decision to `docs/DECISIONS.md` and updated this
  shared handoff. `lessons.md` records the Textual input-binding/System-theme
  proof requirement.
- Selected Textual after comparing it with prompt_toolkit, Urwid, and
  Rich/custom against async, focus/keymap, text editing, command palette,
  responsive layout, mouse, Unicode, testing, packaging, and maintenance needs.
- Recommended launch remains explicit `quotapilot tui`; bare `quotapilot` keeps
  showing help, and all current one-shot/JSON surfaces remain authoritative.
- Navigation is adaptive: a 12-14-cell rail at 88+ columns, optional detail pane
  at 120+, and a single-view destination overlay below 88. 80x24 is a required
  compact acceptance size.
- Arrow/Enter/Esc are the beginner path. hjkl aliases arrows only in navigation
  context. Ctrl+P is global fuzzy discovery; `/` is local filtering; slash
  commands are intentionally excluded.
- A single keymap registry drives actions, the 3-6 item contextual footer, and
  contextual Help. Text inputs retain printable `hjklq/?` behavior and normal
  multi-line editing.
- Execution remains behind Phase 6. Confirmation starts on Cancel, approval
  requires explicit focus, an initial approval is bound to the exact plan, and
  changed escalation must be displayed and approved again.
- Startup publishes persisted/local state first, then performs exactly one
  non-blocking provider-read-only refresh when the provider is already safe and
  authenticated. It never prompts for authentication or triggers execution or
  another provider/account mutation. Failure or ineligibility preserves the
  existing state and its UNKNOWN/STALE semantics; `r` remains the manual
  refresh action. All slow service calls use Textual workers.
- Language reuses `appearance.language`; TUI strings use packaged English and
  Japanese catalogs with terminal-cell-width tests. The proposed additive
  `appearance.tui_theme` supports System/Dark/Light without changing QML GUI
  theming.
- System theme needs an implementation spike because Textual normally renders
  explicit colors and cannot reliably infer terminal background. The normative
  safe fallback is a visibly resolved Dark theme, not environment guessing.

## Phase 9.1 implementation

### Runtime, shell, and service boundary

- `textual>=8.2,<9` resolved to 8.2.8. `quotapilot tui` is registered through
  a lightweight CLI module and imports Textual only inside the command.
- `src/quotapilot/tui/` contains the application shell, composition root,
  immutable state, a plain Overview ViewModel, command/keymap registries,
  localized screens/widgets, three themes, TCSS, and English/Japanese catalogs.
- Overview is the only fully functional destination. Route, Execute, Usage,
  Models, History, Settings, and Doctor are explicitly labeled Phase 9.2
  placeholders; no product behavior is fabricated.
- Widgets call no provider, database, CLI renderer, Qt object, or business
  engine. The Overview ViewModel calls existing `StatusService` and
  `ProviderStatusService`; dependencies are assembled once in `tui/dependencies.py`.

### Startup, navigation, and presentation

- The shell mounts before local I/O. A Textual coroutine worker publishes the
  persisted status, inspects connection/auth without login, then performs one
  live capture only when already connected and authenticated. `r` uses the
  same path, and an active request coalesces later refresh attempts.
- Provider failure keeps valid persisted/UNKNOWN/STALE state and never reflects
  raw exception detail. No startup path executes a task, prompts for auth,
  consumes reset credit, or mutates provider/account configuration.
- At 88+ columns the 14-cell rail remains visible; below 88 it becomes a
  destination overlay; 120+ receives the wide class. Width below 60 or height
  below 18 shows a resize guard. Live resize preserves destination/focus.
- Arrow/Enter/Esc/Tab are primary. hjkl, q, ?, and r are non-priority,
  focus-guarded bindings, verified against both Textual Input and TextArea.
  One key registry produces application bindings, contextual footer hints, and
  Help rows. Ctrl+P uses Textual's fuzzy provider with localized stable commands.
- `appearance.tui_theme` is a strict additive System/Dark/Light setting.
  Textual's ANSI-mode spike could not reliably preserve/detect terminal
  background; System therefore resolves explicitly to Dark and Settings shows
  that resolution. The Qt GUI theme is unchanged.
- The pure locale resolver now lives in `quotapilot.localization`; the GUI
  imports it without behavior change. TUI catalogs are validated for identical
  keys and terminal elision uses Rich cell measurement rather than `len()`.

### Changed file groups and blockers

- Runtime/config: `pyproject.toml`, `uv.lock`, `quotapilot/config/`, and
  `quotapilot/localization.py`.
- Launch/application: `quotapilot/cli/{app,tui}.py` and all files under
  `quotapilot/tui/`.
- Compatibility: `quotapilot/gui/localization.py` now imports the shared pure
  resolver; no QML or GUI layout changed.
- Tests: `test_tui_phase9_1.py` plus additive CLI/config/packaging assertions.
- Documentation: README, changelog, technical design, decisions, handoff,
  Phase 9 contract/design status, and `lessons.md`.
- Blockers: none. Phase 9.2 is intentionally unimplemented, not blocked.

## Phase 9.2A implementation

- `tui/dependencies.py` composes the existing `RoutingService`,
  `ExecutionService`, repository protocol, capability enricher, and profile
  registry. Plain Route/Execute/Models ViewModels hold session-only state;
  screens do not call providers, adapters, CLI commands, or raw SQLite.
- Persisted route evaluation, capability enrichment/projection, execution
  planning, and live-route revalidation run off Textual's event loop with
  `asyncio.to_thread`; provider and adapter I/O remain async.
- Route uses normal multiline TextArea input, asynchronous advisory analysis,
  a concise localized recommendation, UNKNOWN/STALE/profile/provider cues,
  and Details. Ctrl+Enter analyzes; Enter remains text editing in the editor.
  Editing invalidates the prior route, and duplicate analysis is coalesced.
- Dry Run calls `ExecutionService.create_plan(dry_run=True)` and opens Execute
  without invoking the adapter. Real Execute also opens the plan before any
  external call. It displays model, effort, full directory, quota context,
  approval, timeout, attempts, escalation, and a file modification warning.
- Cancel receives initial focus. Only a focused approval gesture starts
  `ExecutionService.run_plan`. A changed escalation plan uses an explicit
  `plan_change_handler` to require another visible approval even when the core
  policy permits automatic low-risk execution. Phase 6 still revalidates quota
  and capabilities before each attempt. Esc cancels through the adapter cleanup
  path; quit during a run opens a confirmation focused on Continue running.
- Models uses the persisted snapshot, existing enrichment, and
  `capability_views`; list/detail and local `/` filtering preserve Unknown
  values. Detail reflows at compact widths, with evidence behind Details.
- New actions, footer/help, English/Japanese catalogs, and theme-token TCSS
  cover the three screens. Very short Execute terminals use a resize guard
  before confirmation. At the end of 9.2A, the four secondary screens were
  still placeholders; Phase 9.2B replaced them.
- Changed files: `src/quotapilot/tui/{app,dependencies,keymap,commands}.py`,
  `src/quotapilot/tui/{screens,viewmodels,styles,locales}/`,
  `src/quotapilot/tui/widgets/chrome.py`,
  `src/quotapilot/services/execution.py`,
  `tests/unit/{test_tui_phase9_2a,test_execution_service}.py`, README,
  changelog, contract/design status, decisions, handoff, and lessons.
- Blockers: none for Phase 9.2A. Real paid execution was not run; normal tests
  use fake adapters and the existing service/adapter boundaries.

## TUI navy visual polish

- `tui/theme.py` now centralizes Dark and Light navy/blue interaction tokens,
  blue-gray/neutral surfaces, subdued selected backgrounds, and independent
  semantic success/warning/error/stale colors. System continues to resolve to
  the same Dark palette; no terminal-background heuristic was added.
- TCSS applies the palette to navigation, model selection, command palette,
  focused editor/filter/detail/actions, and modal borders. Overview retains its
  information hierarchy; connected provider text and normal quota/model values
  are neutral. Overview freshness, Route stale flags, and Models stale labels
  use muted amber. Only a successful execution
  outcome label is green; FAILED and error messages are red. Light muted text
  was darkened to `#647188` for approximately 4.6:1 contrast on its background.
- Changed files: `src/quotapilot/tui/theme.py`,
  `src/quotapilot/tui/styles/quotapilot.tcss`,
  `src/quotapilot/tui/screens/{overview,route,execute,models}.py`,
  `tests/unit/test_tui_phase9_{1,2a}.py`, `docs/{CUI_DESIGN,PHASE9_TUI_CONTRACT,DECISIONS,HANDOFF}.md`,
  `CHANGELOG.md`, and `lessons.md`. No GUI source or interaction logic changed.
- No blocker or remaining visual issue was found in the approved size/language/
  theme matrix. Phase 9.2B and release actions remain outside this task.

## Phase 9.2B implementation

- Usage and History now use bounded repository reads and existing BudgetEngine
  evaluation. Usage shows actual/expected/delta/state/reset, stale/persisted
  status, and a trend only for three comparable samples. History has usage
  list/detail and local filtering; execution history honestly states that no
  execution audit is persisted.
- Settings exposes seven categories, typed selectors and numeric/text controls,
  strict `AppConfig` validation, staged edits, explicit atomic save, and a
  two-step discard confirmation. Language/theme and policy changes apply on
  next TUI launch; Ctrl+P links directly to Language, Theme, and Reserve.
- Doctor renders canonical PASS/WARN/FAIL/SKIP checks with localized names,
  known check reasons/remediations, summary, and safe Settings/Models actions. The default
  offline `DoctorService` runs outside Textual's event loop; `r` coalesces
  duplicate runs. No live capture starts from Doctor.
- All four screens replace Phase 9.1 placeholders. Keymap/footer/help, local
  filtering, English/Japanese catalogs, navy semantic TCSS, and compact
  list/detail reflow are integrated with the existing shell. The installed
  wheel smoke opens all four widgets without provider or database I/O.
- Changed code groups: `src/quotapilot/tui/{app,dependencies,keymap,commands}.py`,
  `screens/{usage,history,settings,doctor}.py`,
  `viewmodels/{usage,history,settings,doctor}.py`, both YAML catalogs, TCSS,
  and `tests/unit/test_tui_phase9_2b.py`. The unused placeholder screen was
  removed. No core routing, budget, execution, or persistence policy changed.
- Blockers: none. Real paid execution was not used.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv build
uv run quotapilot --version
uv run quotapilot --help
uv run quotapilot status --help
uv run quotapilot doctor --help
uv run quotapilot waybar --help
uv run quotapilot config --help
uv run quotapilot models --help
uv run quotapilot execute --help
uv run quotapilot tui --smoke-test
uv run quotapilot gui --smoke-test
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Phase 9.2B default pytest: **530 passed, 5 skipped**. The five skips remain
  the separately gated authenticated provider tests. New Pilot/VM tests cover
  persisted usage, Unknown/Stale/empty/error, history filtering/privacy,
  settings validation/atomic save/deep links/discard, and Doctor states/actions.
- Phase 9.2B visual Pilot: **96 screens rendered** at 80x24, 100x30, and
  140x40 across English/Japanese, Dark/Light, and normal/NO_COLOR for the four
  secondary destinations. Representative compact Japanese Dark screenshots
  were visually inspected; Settings category/detail reflow and Doctor actions
  remained reachable. Ruff, Pyright, and `git diff --check` passed.
- Phase 9.2B wheel/sdist build passed. A clean `/tmp` venv installed the wheel
  and passed TUI smoke (including NO_COLOR), GUI offscreen smoke, and import
  checks for all four new screens from outside the repository. Wheel and sdist
  include the four screens, English/Japanese YAML, and TCSS. Existing CLI and
  GUI tests are included in the full pytest result.
- Navy polish default pytest: **515 passed, 5 skipped**. The skipped tests
  require separately gated authenticated provider access. New token assertions
  cover Dark, Light, System, SUCCESS, OVER, CRITICAL/ERROR, UNKNOWN, and STALE;
  Pilot tests cover semantic execution outcome labels and the existing TUI
  workflows.
- Visual Pilot: **72 screens rendered** for 80x24, 100x30, and 140x40 in
  English/Japanese and Dark/Light across Overview, Route, Execute, Models,
  command palette, and Help. Representative colored screenshots were visually
  inspected with `NO_COLOR` unset, including synthetic SUCCESS/FAILED result
  screens; a separate `NO_COLOR=1` pass remained
  readable through text and focus markers. Screenshots are temporary under
  `/tmp/quotapilot-tui-visual/`, not packaged.
- Ruff: **All checks passed**. Pyright: **0 errors, 0 warnings**.
  `git diff --check`: **PASS**. Wheel and sdist build: **PASS**.
- Local TUI and GUI smoke: **PASS**. Existing CLI tests: **5 passed**. A clean
  `/tmp` venv installed the built wheel and passed installed TUI and GUI smoke
  plus packaged TCSS/theme-token checks from outside the repository.

Historical Phase 9.2A verification:

- Phase 9.2A offline/default pytest: **507 passed, 5 skipped**. The five
  skipped tests require the separately gated authenticated provider run.
- Phase 9.2A Textual Pilot: Route editor/analyze/empty/no-route/UNKNOWN/STALE,
  Dry Run plan, Execute Cancel/approval/changed-plan/success/failure/cancel,
  Models filter/detail, Japanese input, compact/wide reflow, and navigation
  passed. Phase 6 service tests include quota/capability revalidation,
  timeout, bounded attempts, and changed-plan approval.
- Phase 9.2A Ruff: **All checks passed**. Pyright: **0 errors, 0 warnings**.
  `git diff --check`: **PASS**.
- Phase 9.2A wheel and sdist build: **PASS**. Clean wheel installed into a
  separate `/tmp` venv; installed Route/Execute/Models imports, `tui
  --smoke-test`, `gui --smoke-test`, and root/route/execute/models help passed
  without provider access.
- Real execution integration: **NOT RUN**. The normal fake adapter/service
  boundary is the verification gate for this phase.

The following Phase 9.1 results are retained as their historical gate:

- Offline/default pytest: **476 passed, 5 skipped**. The skips are the five
  explicitly gated authenticated tests.
- Phase 9.1 focused/config/CLI/packaging suite: **57 passed**.
- Textual Pilot: **PASS** for Arrow/hjkl, Enter/Esc, Tab/Shift+Tab, Input and
  TextArea printable keys, q context, Ctrl+P English/Japanese discovery,
  contextual Help, manual refresh, refresh coalescing, compact overlay, live
  resize, and every approved size in English/Japanese.
- Visual review: **PASS** for English 100x30 rail layout and Japanese 80x24
  compact layout; full-width labels, metrics, focus, and footer stayed aligned.
- Pseudo-TTY normal launch/q exit: **PASS**; alternate screen, mouse modes,
  cursor, bracketed paste, and terminal contents were restored. The smoke used
  a temporary database and a non-refreshable provider selection.
- Phase 9 design validation: **PASS** for all 28 required CUI headings, required
  implementation-contract topics, requested wireframe coverage, and
  `git diff --check`.
- Startup design validation: **PASS** for persisted-first ordering,
  one eligible background provider refresh, failure/ineligibility retention,
  no automatic authentication or execution, and manual `r` preservation.
- Normal authenticated integration: **5 passed**. It captured quota/models and
  exercised persistence/budget/enrichment/routing only; no model execution.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Build: **wheel and sdist succeeded**; wheel contains TCSS and both YAML catalogs.
- Clean-wheel install: **PASS** after one transient PyPI timeout retry for the
  existing 167 MB `pyside6-addons` dependency. Installed `--version`, `--help`,
  `tui --smoke-test`, `gui --smoke-test`, and config JSON all passed.
- QML lint/offscreen smoke and explicit **900x600** / **1100x720** smoke in
  English and Japanese: **PASS**. Overview, Usage, Route, Execute, History, and
  Settings were rendered with synthetic data in both target combinations;
  bottom-of-page stability, compact/default details, safety information, and
  localized column geometry passed visual review.
- The final wheel and sdist contain both `.ts` and `.qm` catalogs. A clean
  external venv loaded Japanese from the installed wheel (`Overview` -> `概要`)
  and passed GUI smoke without repository-path resource access.
- Calibration: **10/10 acceptable hits**, zero recorded violations.
- Real execution integration: **NOT RUN** and not required for Phase 7.

## Security/privacy review

- Safe YAML loaders remain in use; strict config rejects unknown keys and
  coercible policy values. No arbitrary environment-to-command setting exists.
- Provider/execution subprocesses use argument vectors, never shell task
  interpolation. Phase 7 added no execution subprocess path.
- Fake token/API-key/authorization/account values do not appear in doctor
  output. Status and Waybar regression tests exclude account identity, plan,
  and raw observations while preserving `null`, zero, UNKNOWN, and stale.
- Repository/distribution scans found no credential, real account identity,
  private usage telemetry, raw task, local DB, cache, or virtualenv artifact.
- Normal CI and default pytest cannot execute a paid/real model.

## Remaining limitations

- Linux/Python 3.12 is the verified platform; macOS/Windows are not claimed.
- OpenAI Codex is the only live provider and execution adapter.
- Capability scores remain provisional policy, not empirical guarantees.
- Waybar intentionally reflects the latest persisted snapshot; users must run
  capture/status refresh separately to update it.
- Doctor's non-live auth check depends on the installed Codex CLI's stable
  `login status` behavior; it discards all command output.
- Execution audit persistence, background daemon/notifications, migration
  version 2, and publishing remain unimplemented by design. TUI Execution
  History therefore shows an explicit empty state.
- TUI settings changes, including appearance, apply on next launch so screens
  and the active service graph are not partially reconfigured. GUI language
  remains runtime-retranslated according to its separate existing behavior.
- GUI settings changes are persisted atomically. Language is the sole runtime
  retranslated setting; other changes take effect on the next launch so the
  active service graph is not partially reconfigured.

## Next task

All eight TUI destinations and the v0.1.0 local release gate are complete.
Obtain explicit user release approval before any tag, push, GitHub release, or
package publication. Do not infer publication approval from this gate.

## v0.1.0 final release-candidate review

- Review date: **2026-09-24**. No release, tag, publication, or paid execution
  was performed.
- Default/offline verification: **530 passed, 5 skipped in 56.40s**. All five
  skips are the explicitly gated authenticated Codex integration module; no
  release-critical offline test was skipped. Ruff passed, Pyright reported
  zero errors/warnings, and `git diff --check` passed.
- CLI help/version, Waybar fallback JSON, Doctor JSON/privacy, QML lint,
  offscreen GUI smoke (English/Japanese at 900x600 and 1100x720), TUI smoke,
  NO_COLOR, responsive/theme/localization matrices, and the deterministic
  offline product flow passed.
- `uv build` produced `quotapilot-0.1.0-py3-none-any.whl` and
  `quotapilot-0.1.0.tar.gz`. A clean temporary environment installed the wheel
  and passed CLI, GUI, TUI, lazy-import, and packaged-resource smoke checks.
- Privacy/security review found no unsafe shell/YAML path, credential artifact,
  raw private fixture, unbounded execution output, or default paid-execution
  path. The recorded authenticated provider integration result remains **5
  passed**; it was not rerun during this fresh RC session.
- Release approval remains blocked by repository state rather than an
  implementation defect: Phase 9 changes are still uncommitted, the working
  tree is not clean, and `CHANGELOG.md` still uses `[Unreleased]` instead of a
  finalized v0.1.0 entry. Final human GUI/TUI visual and interaction approval
  also remains a manual release-owner check.

## 2026-09-25 — Git organization and final local release gate

- Phase 9 implementation, tests, and its design records were committed as
  `0af0b19` (`feat: complete interactive TUI`). The v0.1.0 CHANGELOG entry
  was finalized separately as `d1bf755` (`docs: finalize v0.1.0 changelog`),
  leaving an empty `[Unreleased]` section for future work.
- The release owner reports that final GUI/TUI manual review passed. The
  2026-09-24 RC review above remains historical; its Git and CHANGELOG
  blockers were addressed by these commits and this handoff update.
- Final offline gate: `uv run pytest` **530 passed, 5 skipped** (authenticated
  provider tests only); `uv run ruff check .` **passed**; `uv run pyright`
  **0 errors, 0 warnings**; `uv build` produced the v0.1.0 wheel and sdist.
- Local `quotapilot tui --smoke-test`, offscreen `gui --smoke-test`, `--version`,
  and `--help` passed. A clean temporary venv installed the built wheel from
  outside the repository and passed installed CLI version/help, config
  validation, calibration (10/10 acceptable), GUI/TUI smoke, bundled profile
  loading, and packaged TUI locale/TCSS resource checks.
- Changed for this RC record: `docs/HANDOFF.md` only. No implementation changes
  were needed. No paid execution, tag, push, release, or publication occurred.
- Blockers: none for the local gate. Next action: final user release approval;
  any tag, push, GitHub release, or publication needs an explicit instruction.
