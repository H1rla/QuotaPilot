# QuotaPilot Phase 9 — Interactive Terminal UI Contract

Status: Normative implementation contract; Phase 9.2A and 9.2B screens implemented
Phase: 9
Depends on:

- completed QuotaPilot core through Phase 7;
- completed Phase 8/8.1 desktop GUI, without redesigning it;
- `docs/CUI_DESIGN.md`;
- existing status, budget, routing, execution, persistence, configuration, and
  Doctor boundaries.

Last design update: 2026-09-24

## 1. Purpose and phase boundary

Phase 9 adds a persistent interactive terminal application:

```bash
quotapilot tui
```

It is the third frontend, alongside the one-shot CLI and desktop GUI. It must
call the same core services directly, preserve existing CLI automation and JSON
contracts, and preserve Phase 6 execution authorization.

Phase 9.1, 9.2A, and 9.2B implementations were separately authorized. All
eight primary TUI destinations are implemented. Release tagging, a GitHub
release, and publication remain separate actions.

## 2. Framework evaluation

Evaluation baseline rechecked on 2026-09-23:

| Candidate | Strengths | Costs/risks | Fit |
|---|---|---|---|
| **Textual 8.2.x** | asyncio-native application model; screens, focus, bindings, mouse events, Input/TextArea, responsive CSS/layout, built-in fuzzy Ctrl+P palette, worker lifecycle, Rich rendering, Pilot key/click testing | largest dependency set; fast-moving major API; terminal-default System theme needs an implementation spike | **Selected** |
| prompt_toolkit 3.0.x | excellent terminal text editing, Unicode double-width support, asyncio, focus-aware bindings, mouse, lightweight | lower-level full-screen composition; command palette, responsive widget system, view lifecycle, contextual footer, and higher-level test harness require more custom application infrastructure | Runner-up, not selected |
| urwid 4.1.x | mature widget/canvas model, Unicode and mouse support, multiple event-loop adapters | older low-level composition model; async updates may need explicit redraw; more custom responsive, palette, theming, and interaction-test work | Not selected |
| Rich 15.x/custom | excellent rendering, layout, live display, Unicode; already familiar through Typer output | not a full input/focus/widget application framework; QuotaPilot would own event dispatch, editor, mouse, focus, overlays, palette, resize, and test driver | Rejected for maintenance burden |

The comparison against Phase 9 requirements is:

| Criterion | Textual 8.2.x | prompt_toolkit 3.0.x | Urwid 4.1.x | Rich 15.x/custom |
|---|---|---|---|---|
| Python/core integration | direct typed Python calls | direct typed Python calls | direct typed Python calls | direct calls, but application shell is custom |
| Async | native coroutine workers, cancellation, exclusive groups | asyncio application/background tasks | asyncio event-loop adapter; redraw coordination remains explicit | rendering only; event loop and cancellation are custom |
| Event/focus model | DOM events, screens, focus-aware bindings | strong filters, buffers, focusable containers | widget `keypress`/`mouse_event` dispatch | must be designed and maintained |
| Arrow/hjkl contexts | declarative bindings with focused-widget precedence | precise conditional key filters | widget overrides and unhandled input | must be designed and maintained |
| Mouse | click/move/scroll events | cursor/scroll/click support | click/scroll events | Rich renders; input integration is custom |
| Responsive layout | CSS/grid/dock plus resize events/classes | conditional containers and manual dimension logic | canvas/container sizing and manual breakpoints | flexible render layout, custom focus/reflow lifecycle |
| Styling/themes | registered themes and TCSS variables | style system, assembled per control/layout | terminal palettes | excellent rendering styles, no widget theme system |
| Unicode/Japanese | Rich cell measurement; IME still needs manual proof | explicit double-width/wcwidth support | basic Unicode width support | Rich cell measurement; editor still custom |
| Testing | `run_test` and Pilot key/click/size driver | pipe input and dummy output | lower-level widget/event tests | no integrated interaction driver |
| Command palette | built-in fuzzy Ctrl+P surface/providers | build from buffers/completion/layout | build as an overlay/widget flow | build palette and input stack |
| Text input | maintained Input and multiline TextArea | strongest editor primitives | capable Edit widget, more app assembly | full editor must be built or added |
| Packaging | one direct dependency plus packaged TCSS/catalogs | lighter dependency, more QuotaPilot code | mature dependency, more QuotaPilot code | Rich is already transitive, but custom framework code dominates |
| Maintenance burden | moderate; isolate fast-moving APIs | high for full application structure | high for responsive/palette/test infrastructure | highest |

The version check found Textual 8.2.8, prompt_toolkit 3.0.52, Urwid 4.1.5,
and Rich 15.0.0 as the current reviewed releases. These observations justify
the major-line comparison but do not replace dependency resolution at the
implementation gate.

Official capabilities consulted:

- [Textual command palette](https://textual.textualize.io/guide/command_palette/)
- [Textual workers](https://textual.textualize.io/guide/workers/)
- [Textual input and focus](https://textual.textualize.io/guide/input/)
- [Textual testing](https://textual.textualize.io/guide/testing/)
- [Textual layout](https://textual.textualize.io/guide/layout/)
- [prompt_toolkit full-screen applications](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html)
- [prompt_toolkit asyncio](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/advanced_topics/asyncio.html)
- [Urwid main loop](https://urwid.org/manual/mainloop.html)
- [Rich layout](https://rich.readthedocs.io/en/stable/layout.html)
- [Textual package/release metadata](https://pypi.org/project/textual/)
- [prompt_toolkit package/release metadata](https://pypi.org/project/prompt-toolkit/)
- [Urwid package/release metadata](https://pypi.org/project/urwid/)
- [Rich package/release metadata](https://pypi.org/project/rich/)

### 2.1 Selection

Phase 9 SHALL use **Textual**.

The implementation baseline is:

```text
textual >= 8.2, < 9
```

The exact lower bound and lockfile resolution must be rechecked when
implementation starts. Any change of major version requires rerunning the
framework spike and updating this contract before production code depends on
new APIs. Do not install the `syntax` extra; QuotaPilot does not need
tree-sitter highlighting for Phase 9.

Textual is selected because it supplies the product's hardest cross-cutting
requirements—focus, normal text input, async work, fuzzy command discovery,
responsive layout, mouse, and interaction testing—as one coherent framework.
The TUI must still isolate framework types at the terminal-view boundary so
core and plain state mapping tests do not require a running terminal app.

## 3. Required architecture

Dependency direction:

```text
QuotaPilot Core Services / Engines / Repository Protocols
                         ↓
              TUI Application / ViewModels
                         ↓
                  Textual Views / Widgets
```

More concretely:

```text
Typer `tui` command
  -> lazy import of TUI launcher
  -> TUI composition root
  -> existing typed services and policies

Textual App
  -> navigation / overlay / execution coordinator
  -> plain TUI ViewModels and immutable display state
  -> Screens and Widgets
```

Forbidden:

```text
TUI -> subprocess("quotapilot status")
TUI -> Typer render functions
TUI -> GUI QObjects or QML
TUI -> raw OpenAI RPC
TUI -> raw SQLite connection
TUI -> duplicated budget/routing/execution policy
Screen/Widget -> provider, repository, or execution adapter directly
```

Allowed core composition follows current GUI precedent:

- `StatusService` and `ProviderStatusService` for Overview;
- `RoutingService` for Route;
- `ExecutionService` for plans and controlled execution;
- `DoctorService` for Doctor;
- `SnapshotRepository` protocol plus `BudgetEngine` for historical usage, as
  no history service currently exists;
- `CapabilityEnricher` and `ModelProfileRegistry` over a repository snapshot
  for Models;
- `load_effective_config` and `save_user_config` for Settings.

Calling the repository protocol and pure engines is not raw persistence or
duplicated business logic. If a frontend-neutral history/model service is added
later, the TUI must migrate to it rather than preserve parallel composition.

### 3.1 Relationship to GUI ViewModels

The Qt ViewModels are architectural evidence, not reusable dependencies. They
inherit `QObject`, expose QML-shaped dictionaries, and contain Qt translation
assumptions. Phase 9 SHALL create plain TUI ViewModels/state mappers over the
same service result models. It SHALL NOT import `quotapilot.gui`.

Small genuinely frontend-neutral helpers may be extracted only when both
frontends can use them without importing Qt or Textual. Such extraction must be
a separate minimal diff with existing GUI tests green; it must not restyle or
restructure QML.

## 4. Package structure

The normative Phase 9 package shape is:

```text
src/quotapilot/
├── cli/
│   └── tui.py                  # lazy Typer launch adapter only
├── localization.py            # frontend-neutral locale resolution
└── tui/
    ├── __init__.py
    ├── app.py                  # Textual App and launch/smoke entry
    ├── dependencies.py         # TUI composition root
    ├── controller.py           # navigation, overlays, app-level execution
    ├── commands.py             # stable command descriptors/providers
    ├── keymap.py               # bindings + footer/help metadata
    ├── localization.py         # catalog loading and interpolation
    ├── state.py                # immutable presentation-state types
    ├── screens/
    │   ├── base.py
    │   ├── overview.py
    │   ├── route.py
    │   ├── execute.py
    │   ├── usage.py
    │   ├── models.py
    │   ├── history.py
    │   ├── settings.py
    │   ├── doctor.py
    │   ├── help.py
    │   └── confirmation.py
    ├── viewmodels/
    │   ├── base.py
    │   ├── overview.py
    │   ├── route.py
    │   ├── execute.py
    │   ├── usage.py
    │   ├── models.py
    │   ├── history.py
    │   ├── settings.py
    │   └── doctor.py
    ├── widgets/
    │   ├── chrome.py
    │   ├── navigation.py
    │   ├── contextual_footer.py
    │   ├── state_text.py
    │   └── action_row.py
    ├── styles/
    │   └── quotapilot.tcss
    └── locales/
        ├── en.yaml
        └── ja.yaml
```

Files SHALL be created only as implementation needs them; do not generate empty
stubs to mirror the tree. A screen-specific widget remains with its screen
until actual reuse justifies promotion to `widgets/`.

## 5. Launch behavior and CLI compatibility

### 5.1 Normative Phase 9 behavior

| Invocation | Behavior |
|---|---|
| `quotapilot tui` | launch the full-screen TUI |
| `quotapilot tui --help` | show command help and exit without initializing Textual |
| `quotapilot --help` | show root help, including `tui`; never launch TUI |
| `quotapilot` | retain current `no_args_is_help=True` behavior |
| `quotapilot status` and all existing commands | unchanged |

The root app SHALL register `tui` through `src/quotapilot/cli/tui.py`. That
module SHALL import Textual/TUI code only inside the command function, following
the existing lazy GUI launch pattern. Existing CLI invocations must not pay a
Textual import/startup cost.

`quotapilot tui` requires interactive stdin/stdout. In a non-TTY environment it
SHALL exit with a stable concise error that directs the user to one-shot CLI
commands; it SHALL NOT emit control sequences or fall back to an unrelated
command.

The TUI should use the alternate screen and restore the prior terminal state on
normal exit, cancellation, and uncaught failure.

### 5.2 Recommendation for bare `quotapilot`

Do **not** make bare `quotapilot` launch the TUI in Phase 9, and retain help as
the long-term default unless a major-version compatibility decision changes it.

Reasons:

- existing users and shell documentation already receive help;
- a full-screen launch is surprising in scripts, pipes, editor tasks, and
  non-interactive shells;
- TTY detection reduces but does not remove expectation and accessibility
  changes;
- `quotapilot tui` is short, explicit, and discoverable in root help.

If reconsidered later, it requires a separately approved compatibility plan,
TTY gating, release notes, and an escape hatch. Phase 9 tests must pin the
current no-argument behavior.

### 5.3 Existing commands and JSON

These surfaces SHALL remain valid and retain existing exit/status semantics:

```text
quotapilot status
quotapilot budget
quotapilot models
quotapilot route
quotapilot execute
quotapilot doctor
quotapilot config
quotapilot waybar
quotapilot snapshot
quotapilot calibrate
quotapilot gui
```

No field may be removed, renamed, retyped, or given different semantics in an
existing JSON report because of Phase 9. The TUI must consume typed service
models, not parse CLI JSON.

The only planned additive configuration output is
`appearance.tui_theme`; its addition to `config show --json` must be documented
and tested as an additive schema extension. No other existing JSON shape should
change.

## 6. Application state and screen lifecycle

The application controller owns:

- current destination and navigation back stack;
- current layout mode;
- details visibility per destination;
- command/help/confirmation overlays;
- in-memory Route draft and last recommendation;
- the current ExecutionPlan and execution operation;
- active language/theme;
- global provider/execution indicator text.

Screens own transient selection, scroll, and filter state. ViewModels own
service calls and immutable UI-ready state. Widgets render and emit intents;
they do not orchestrate services.

When returning to a previously visited screen, list selection/filter/scroll may
be retained for the session. Sensitive task text and execution output are never
persisted as navigation state.

## 7. Mandatory screens

### 7.1 Overview

MUST show the binding pool's remaining fraction, state, reset, today's budget,
pressure, freshness/source, provider status, and current in-memory route
recommendation when available. Without a recommendation it MUST show a Route
CTA, not invent a generic model choice.

On startup, Overview MUST publish persisted/local status before waiting on any
provider call. It MUST then inspect provider status without launching an
authentication flow. When the provider is already connected and authenticated
and the selected adapter path is verified to perform provider-side reads only,
the application MUST start exactly one background
`StatusService.get_status(..., refresh_provider=provider)` operation for that
TUI launch. Local persistence of the returned coherent snapshot by
`StatusService` is expected; the automatic operation MUST NOT execute a task,
consume reset credit, start login, or mutate provider/account configuration.

Persisted values remain visible with a quiet `Refreshing...` status while the
worker runs. Success publishes the refreshed report. Failure MUST retain the
usable persisted report with authoritative persisted-fallback, UNKNOWN, and
STALE semantics. If provider state is unavailable, unauthenticated, unknown,
or otherwise unsafe for automatic refresh, the application MUST skip the
provider call, preserve the current report, and show an actionable status.
`r` remains the explicit manual refresh action.

### 7.2 Route

MUST provide normal multi-line task input, Analyze, concise TaskProfile,
recommendation, explanation, escalation, Details, Dry Run, and Execute. It MUST
call `RoutingService`; analysis has no execution side effect. Raw task text
stays in memory.

### 7.3 Execute

MUST create plans and run them only through `ExecutionService`. Before a real
attempt it MUST show model, effort, full working directory, quota context,
approval requirement, timeout, attempts, escalation, and file-modification
warning.

Initial confirmation focus MUST be Cancel. After the user approves the visible
initial plan, the controller may pass a one-shot approval for that exact
`ExecutionPlan` into the service approval handler so the same plan is not shown
twice. Equality must bind all material plan fields, not only `execution_id`.
Any different candidate delivered to the approval handler MUST suspend on a new
visible confirmation. A prior click/Enter may not approve a materially changed
escalation.

Execution state MUST be application-owned rather than tied to a disposable
screen worker. Navigating away may keep it running with a visible global status;
quitting or cancelling must invoke and await the existing cleanup path.

### 7.4 Usage

MUST show actual, expected, delta, state, and reset for persisted samples.
The primary Usage visualization is the shared left-to-right daily forecast
strip; narrow terminals may wrap chronological groups into two rows.
Repository reads are bounded. Budget evaluation uses the existing engine.

### 7.5 Models

MUST use list/detail. The list shows ID, freshness, and routability. Details
show selectable/routable, power/cost/latency, explicit effort order, profile,
freshness, confidence, evidence, provenance, and warnings. Unknown metadata
remains Unknown.

### 7.6 History

MUST visibly separate Usage history and Execution history. Usage comes from
persisted snapshots. Execution history is the explicit privacy-safe empty state
until a future core contract adds persistence. No raw task text may be shown.

### 7.7 Settings

MUST expose General, Budget, Routing, Execution, Models & Profiles,
Integration, and Appearance categories through category/list detail. It MUST
load one `AppConfig`, validate changes with authoritative strict models, and
save atomically through `save_user_config`.

Language and TUI theme MAY apply live after successful save. Other settings
MUST state that they apply on next launch.

### 7.8 Doctor

MUST call `DoctorService` directly and show PASS/WARN/FAIL/SKIP, summary,
details, reason, and remediation. Default rerun is offline. A live check is an
explicit separate action and does not persist provider capture.

## 8. Keybinding contract

Canonical bindings:

| Context | Keys | Action |
|---|---|---|
| Navigation | `j`, `Down` | next item |
| Navigation | `k`, `Up` | previous item |
| Navigation | `h`, `Left` | previous region/back when advertised |
| Navigation | `l`, `Right` | next region/open when advertised |
| Navigation/modal | `Enter` | activate visibly focused item |
| All overlays/forms | `Esc` | safe close/cancel/back |
| Navigation/form/modal | `Tab`, `Shift+Tab` | focus traversal |
| Global | `Ctrl+P` | command palette |
| Navigation | `?` | contextual help |
| Supported list | `/` | local filter |
| Screen-specific | `r` | refresh/rerun only when advertised |
| Navigation | `Ctrl+D` | toggle Details |
| Clean navigation | `q` | quit |
| Route editor | `Ctrl+Enter` | Analyze fast path |

Implementation SHALL define bindings once in `keymap.py` as stable action IDs,
keys, message IDs, contexts, visibility, and priority. Screens, footer, and help
derive from that registry; they may not maintain independent shortcut labels.

Printable navigation bindings SHALL NOT be priority bindings. Focused
`Input`/`TextArea` must consume printable characters. App/screen action handlers
must additionally guard against applying navigation actions while a text editor
has focus. Tests must type `hjklq/?` into every text-control class.

`Ctrl+P` and the topmost-modal Esc handling may be priority bindings.
`Ctrl+D` is disabled as a details shortcut while text input is focused so the
editor retains its normal operation.

## 9. Focus and confirmation behavior

- Every screen declares focus regions in reading order.
- `Tab` changes regions/controls; list movement does not create hundreds of tab
  stops.
- Wide list/detail screens use rail -> list -> detail/actions order.
- Standard uses rail -> content/actions.
- Compact uses content/actions; Left from root opens the destination overlay.
- Opening detail transfers focus into detail; Esc/Left returns to the prior
  selected list row.
- Closing palette/help/filter restores previous focus.
- Disabled/hidden actions are removed from focus order.
- Loading does not move focus unless the focused control disappears.

Execution confirmation has two focusable actions in this order:

```text
Cancel -> Approve & Execute
```

It opens on Cancel. Enter on Cancel cancels. A pointer click on approval is an
explicit focus-and-activate gesture and is permitted, but it passes through the
same exact-plan approval callback.

## 10. Command architecture

Use Textual's command-palette screen and provider API, but supply a QuotaPilot
command registry with stable IDs. Do not use translated display strings as
identifiers.

Each command descriptor contains:

```text
id
title_message_id
help_message_id
keywords
availability predicate
callback/action ID
discovery priority
```

Search uses Textual's fuzzy matcher over localized title/help plus stable
keywords. Empty-query discovery is quick and context-sensitive. Provider
startup/search must not perform provider, database, routing, or execution work;
commands trigger normal application intents after selection.

The palette includes navigation and safe actions only. `Execute` navigates;
approval is never a palette command. Slash commands are not implemented.

## 11. Async and concurrency requirements

Textual's event/message loop MUST never await a slow service call inline in a
key or input handler.

Use coroutine workers for existing async services:

- persisted status and snapshot reads;
- provider inspection/refresh;
- routing;
- execution planning and execution;
- Doctor checks.

Use a thread worker only for genuinely synchronous bounded I/O such as the
current atomic configuration writer. UI mutations from a thread worker must be
posted back through Textual's supported main-thread mechanism.

Requirements:

- initial shell renders before data access;
- startup loads and publishes persisted/local status before beginning a
  provider refresh;
- provider status inspection never launches an authentication prompt or login
  RPC;
- after that inspection, exactly one startup refresh per TUI launch runs only
  when the provider is already connected/authenticated and the adapter path is
  verified as provider-side read-only;
- unsafe, unavailable, unauthenticated, or unknown provider state skips the
  automatic refresh and produces an actionable status without replacing the
  persisted report;
- refresh failure preserves the current report and its persisted-fallback,
  UNKNOWN, and STALE semantics;
- the active view shows a quiet local `Refreshing...` indicator while retaining
  useful content;
- `r` starts an explicit manual refresh; a request made while a refresh is
  active is coalesced rather than creating a concurrent provider operation;
- no startup worker may execute a task, consume reset credit, start login, or
  mutate provider/account configuration;
- repeated refresh/analyze/filter work uses exclusive worker groups or
  generation IDs so stale completion cannot overwrite newer state;
- workers tied to a removed ordinary screen are cancelled;
- the application-level execution worker survives navigation but not confirmed
  application shutdown;
- cancellation must flow to `ExecutionService` and the adapter cleanup path;
- worker failures map to stable UI errors and do not expose raw exception text;
- no full-screen loading state is used when prior useful content exists.

Normal CI uses fake/in-memory dependencies. Authenticated provider capture and
real execution retain their existing explicit integration gates.

## 12. Localization contract

Phase 9 reuses `AppConfig.appearance.language` and its values
`system | en | ja`.

The pure locale resolver SHALL move to a frontend-neutral module that accepts a
preference and a supplied system locale. The GUI may import this pure helper,
but no TUI module may import PySide6 or Qt translation types. Unknown system
locales fall back to English.

TUI copy uses stable message IDs in packaged `en.yaml` and `ja.yaml` catalogs.
Catalog loading SHALL use `yaml.safe_load`, validate mapping/string types, and
require identical key sets in tests. English is the source/fallback. Missing
messages fail tests and fall back to the English message at runtime; they must
not crash the app.

Identifiers, paths, model/provider IDs, config keys, enum values presented as
technical data, and literal CLI commands remain canonical. User-facing state
labels, help, footer descriptions, actions, errors, and settings labels are
translated.

Layout and truncation SHALL use framework/Rich cell measurement (`wcwidth`
semantics), never `len()`. Acceptance includes Japanese full-width text,
combining marks, long labels, resize, and IME/paste manual checks.

## 13. Responsive layout contract

One central resize policy computes:

```text
WIDE         columns >= 120
STANDARD     88 <= columns < 120
COMPACT      60 <= columns < 88
CONSTRAINED  columns < 60
```

and vertical density:

```text
NORMAL       rows >= 30
SHORT        24 <= rows < 30
VERY_SHORT   18 <= rows < 24
UNSAFE       rows < 18
```

Screens apply common Textual classes/state for these modes rather than each
inventing breakpoints. Resize preserves current destination, selected domain
item, and safe focus where possible.

- Wide: rail + main + optional details.
- Standard: rail + main; details replace main or use a modal/full view.
- Compact: collapsed rail, one focused view, destination overlay.
- Constrained: read-only summaries may scroll; execution approval and settings
  save show a resize guard when safety-critical content cannot fit.

No main screen or primary workflow uses horizontal scrolling. DataTable is not
the default for Models or History; list/detail is required.

Acceptance sizes are at least:

```text
140x40
120x30
100x30
80x24
72x20
60x18
```

in English and Japanese. Below 60x18, terminal restoration, Help, and Quit must
still work even when the app asks the user to resize.

## 14. Theme contract

Phase 9 adds a strict enum:

```text
appearance.tui_theme = system | dark | light
```

Default is `system`. It is an additive field in the existing central config,
not a separate dotfile and not a request to change the QML GUI theme.

Register exactly three QuotaPilot Textual themes. Use semantic variables for
accent, foreground, background, surface, panel, warning, error, success, and
muted text. TCSS must use variables; scattered color literals are forbidden.

- Dark uses deep navy-black, muted blue-gray surfaces, and restrained blue focus.
- Light uses a separately contrast-tested off-white palette and darker navy/blue focus.
- System first attempts terminal-default foreground/background/ANSI behavior
  supported by the pinned Textual/Rich stack. Because Textual normally renders
  explicit RGB themes and does not reliably discover terminal background,
  implementation MUST begin with a small spike. If default cells cannot be
  preserved readably, System resolves to Dark, exposes `Resolved: Dark` in
  Settings/Doctor, and records the limitation; it must not guess from
  `COLORFGBG` or similar non-portable heuristics.

Semantic state always includes text. Green is reserved for explicit SUCCESS;
normal provider connection and ordinary quota values remain neutral. OVER and
STALE remain amber, CRITICAL and ERROR red, and UNKNOWN gray. `NO_COLOR` and
reduced color depth must retain markers, reverse/weight, and text labels.

## 15. Loading and error-state contract

Each ViewModel state distinguishes at least:

```text
initial
loading
ready
refreshing
empty
unavailable
error
```

Domain/display values independently retain:

```text
UNKNOWN
STALE
Not authenticated
Using persisted data
```

No mapper converts `None` to zero or a healthy label. Refresh failure preserves
prior state and source/freshness. Empty states contain a valid next action.
Normal UI errors never display a traceback or arbitrary provider/adapter
exception string. Debug logging must retain existing redaction and must not log
task text, palette queries, full execution output, credentials, or raw provider
responses.

## 16. Privacy contract

- Route task text remains memory-only.
- Palette/filter queries are not persisted or logged.
- Usage History reads privacy-transformed snapshots.
- Execution History remains empty until a core persistence contract exists.
- Account IDs, plan inference, credentials, tokens, cookies, raw provider
  payloads, environment contents, and unbounded output are never shown.
- Execution displays only bounded/redacted summaries supplied by Phase 6.
- Clipboard copy is never automatic. A future copy action must be visible and
  must not copy hidden/raw metadata.
- Textual devtools/console is not enabled in production launch.

## 17. Safety contract

Phase 9 SHALL NOT weaken Phase 6.

- Route does not execute.
- Dry Run invokes no external model.
- Real execution requires an inspectable plan and explicit focused approval.
- Working directory remains visible in confirmation.
- `Esc` cancels approval.
- Palette and global shortcuts cannot approve.
- Approval is for the exact plan presented.
- Changed quota/capability/recommendation follows service invalidation.
- Every materially different escalation is presented and approved again.
- Retry/escalation remain bounded by existing policy.
- Authentication/user cancellation do not become escalation signals.
- Quit during execution cannot orphan a subprocess.
- A terminal resize must never hide the warning or turn Enter into approval; an
  unsafe confirmation layout becomes a resize guard.

## 18. Mouse contract

Enable Textual mouse support when available. Click selection, buttons, focus,
footer actions, and wheel scrolling are permitted. Keyboard behavior remains
authoritative. Mouse actions dispatch the same action IDs and confirmation
path. No behavior depends on hover, right click, drag, or double click.

## 19. Testing contract

### 19.1 Pure unit tests

Cover:

- service-model to immutable TUI-state mapping;
- UNKNOWN/STALE/unavailable preservation;
- localized catalog completeness and fallback;
- command availability and fuzzy search inputs;
- single-source keymap/footer/help derivation;
- cell-width-aware truncation with Japanese/combining characters;
- theme resolution and System fallback;
- settings validation and dirty-state handling;
- execution approval state machine independent of Textual rendering.

### 19.2 Textual Pilot tests

Use `App.run_test(size=...)` and `Pilot` to cover:

- root launch, destination rail, and compact destination overlay;
- arrow and hjkl equivalence in navigation;
- `hjklq/?` behaving as text in Input/TextArea;
- Tab/Shift+Tab focus traversal;
- Ctrl+P discovery, filtering, activation, and focus restoration;
- `/` local filtering and Esc clear/close behavior;
- contextual Help content;
- Ctrl+D details behavior outside and inside text input;
- Overview persisted/local publication before the one eligible startup refresh,
  including success, failure retention, unsafe-state skip, and manual `r`;
- Route analyze -> Dry Run/Execute transition;
- execution initial Cancel focus;
- Enter not executing until approval is focused;
- Esc cancelling confirmation;
- fresh confirmation for changed escalation;
- mouse click/scroll parity;
- resize transitions and no horizontal overflow;
- active execution navigation/quit cancellation behavior.

Run the acceptance size matrix in English and Japanese. Assertions should
inspect focus, state, visible text, and geometry; avoid fragile whole-screen
snapshots as the only evidence.

### 19.3 Service and compatibility tests

- Fake delayed services prove the UI remains responsive and stale worker
  completions cannot win.
- Normal tests never require authenticated provider access.
- Normal tests never run a real model.
- Existing CLI test suite remains green.
- Golden/contract assertions confirm existing JSON fields and semantics.
- Root no-argument help behavior is pinned.
- Import tests prove existing CLI commands do not import Textual.

### 19.4 Manual terminal checks

Verify at least the project-supported Linux terminal plus tmux/SSH where
available:

- terminal restore after normal exit, Ctrl+C, and failure;
- Japanese IME input and paste;
- 16-color, 256-color, truecolor, `NO_COLOR`;
- mouse on/off;
- ambiguous/double-width glyph alignment;
- 80x24 execution confirmation and resize during confirmation.

## 20. Packaging contract

During implementation:

- add Textual as a direct runtime dependency with the reviewed major bound;
- do not add `textual-dev` to runtime dependencies;
- update `uv.lock`;
- package TCSS and locale YAML under `quotapilot/tui/`;
- keep PySide6/QML resources unchanged;
- register `quotapilot tui` through the existing console script/Typer app;
- retain lazy import for TUI and GUI entry commands;
- add a hidden `quotapilot tui --smoke-test` or equivalent deterministic
  installed-wheel smoke that mounts the app headlessly and exits without
  provider access;
- verify wheel/sdist resource inclusion and clean-wheel launch.

Do not split TUI into a separate distribution in Phase 9. QuotaPilot currently
ships the GUI dependency in the primary package; one complete package keeps all
three documented frontends available. Packaging modularization requires a
separate product decision.

## 21. CLI compatibility risks and mitigations

| Risk | Required mitigation |
|---|---|
| Root command accidentally starts full-screen UI | retain `no_args_is_help=True`; pin test |
| Textual imported by scripts | lazy import only inside `tui` command; import regression test |
| Typer binding/option collision | TUI options live under `quotapilot tui`; existing commands unchanged |
| JSON renderer reused or changed | consume service models directly; existing JSON golden tests |
| Non-TTY control-sequence output | preflight TTY check and stable error |
| Config output gains theme field | document/test additive `appearance.tui_theme`; no other shape changes |
| Ctrl+C/exception leaves terminal altered | Textual lifecycle plus explicit smoke/manual restore tests |
| Root help becomes too slow | `tui` module remains lightweight; no Textual import during help |

## 22. Terminal and i18n risks

| Risk | Required response |
|---|---|
| Japanese double-width/combining glyph drift | framework cell measurement; no `len()` padding; bilingual size tests |
| Ambiguous-width glyph differs by terminal | avoid column-critical decorative glyphs; retain gutters and text labels |
| IME behavior cannot be fully simulated | target-terminal manual acceptance |
| Very long Japanese action label | adaptive vertical actions/elision with full help text; never clip approval meaning |
| Truecolor unavailable | semantic 16-color/monochrome fallbacks |
| Terminal background cannot be detected | no heuristic guess; System fallback disclosed |
| Resize during modal | recompute layout; preserve safe focus; block unsafe approval layout |
| Key aliases differ by terminal | test Textual key names and retain arrow/Tab beginner paths |

## 23. Non-goals

Phase 9 does not implement:

- new budget, routing, capability, or execution business logic;
- a replacement for one-shot CLI commands or JSON;
- a terminal clone of the desktop GUI;
- a Vim editing mode;
- slash commands or a generic terminal shell;
- file browsing/management;
- autonomous or command-palette execution approval;
- raw provider inspection;
- execution-audit persistence;
- background daemon/notifications;
- GUI theme redesign;
- release tagging, GitHub release, or PyPI publication.

## 24. Completion criteria

Phase 9 implementation is complete only when:

1. `quotapilot tui` launches from a clean installed wheel.
2. Bare `quotapilot`, `--help`, every existing command, and existing JSON
   contracts remain compatible.
3. Textual is lazily imported only for the TUI command.
4. All eight mandatory destinations meet `CUI_DESIGN.md`.
5. The adaptive rail/palette navigation works at wide, standard, and compact
   widths.
6. Beginner Arrow/Enter/Esc flows and expert hjkl/Ctrl+P/search flows are both
   complete.
7. Printable navigation keys behave normally in text input.
8. Contextual footer and Help derive from the same keymap metadata.
9. Local filter and global command palette are distinct; slash commands are
   absent.
10. Overview is persisted-first, performs one eligible provider-read-only
    startup refresh without blocking first render, preserves usable state on
    failure/unsafe provider state, and retains manual `r` refresh.
11. Route calls existing routing and never auto-executes.
12. Execute uses Phase 6, starts on Cancel, requires exact-plan approval, and
    re-prompts changed escalation.
13. No service/database/provider/execution operation freezes the event loop.
14. UNKNOWN, STALE, unavailable, authentication, loading, error, and empty
    states pass tests.
15. System/Dark/Light and reduced-color behavior preserve focus and semantics.
16. English/Japanese layout passes the acceptance matrix and manual IME check.
17. Privacy and bounded-output review passes.
18. Pilot, unit, lint, type, full pytest, build, and clean-wheel smoke pass.
19. Normal CI remains independent of authenticated provider access and real
    execution.
20. GUI tests and installed GUI smoke remain green without visual redesign.
21. `docs/HANDOFF.md` and `docs/DECISIONS.md` reflect the completed phase.
22. No release action is performed.

## 25. Proposed design decisions for user review

This draft recommends the following policies. They become the Phase 9
implementation baseline only after user review; a later approved design
revision may supersede them:

1. Textual 8.2.x major line as the implementation baseline.
2. Explicit `quotapilot tui`; bare `quotapilot` continues to show help.
3. Persistent narrow rail at 88+ columns and collapsed navigation below 88;
   80x24 uses the compact single-view layout.
4. No slash-command grammar; `/` is local filtering only.
5. Startup publishes persisted/local state first, then performs one
   non-blocking provider-read-only refresh when the current provider state is
   safe; failure or ineligibility preserves that state, and `r` remains.
6. `appearance.tui_theme` is an additive central-config field and does not
   change the GUI theme.
7. System theme falls back visibly to Dark if terminal-default surfaces cannot
   be made reliable in the pinned Textual version.

Review of this design does not itself authorize Phase 9 implementation. Coding
still requires a separate explicit implementation request.
