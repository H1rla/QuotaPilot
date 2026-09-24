# QuotaPilot Interactive Terminal UI Design

Status: Normative UX/UI design specification; Phase 9.2A and 9.2B screens implemented
Scope: Persistent full-screen terminal application (`quotapilot tui`)
Implementation status: All eight primary destinations implemented; release approval remains separate
Last design update: 2026-09-24

This document uses **TUI** for the product surface and **terminal cell** for its
layout unit. The filename retains `CUI` only because it is the requested project
artifact name.

## 1. Design goals

QuotaPilot has three complementary frontends:

```text
CLI  -> one-shot commands, scripts, automation, JSON
TUI  -> persistent keyboard-driven daily use
GUI  -> graphical desktop application
```

The TUI must combine:

```text
low learning curve + high expert efficiency
```

The governing interaction promise is:

> A beginner can use the whole product with Arrow keys, Enter, and Esc. An
> experienced user can accelerate the same workflows with hjkl, Ctrl+P, local
> search, and a small set of contextual shortcuts.

The TUI must be:

- calm, minimal, technical, terminal-native, and precise;
- keyboard-complete without requiring Vim knowledge;
- information-dense without becoming a dashboard of boxes;
- immediately useful from persisted local state;
- explicit about uncertainty, freshness, provider failures, and execution risk;
- a presentation layer over QuotaPilot services, not a second core.

The TUI must not copy the QML GUI layout. It shares the product information
hierarchy, safety model, configuration, and restrained navy/blue interaction
accent, then uses terminal-native lists, focus regions, overlays, and text editing.

### Transferable reference patterns

QuotaPilot borrows interaction principles, not layouts or branding:

| Reference | Transferable principle | QuotaPilot use |
|---|---|---|
| [OpenCode](https://opencode.ai/v2/docs/cli/tui/) | sparse developer-tool chrome, contextual commands, Ctrl+P discovery | calm shell and first-class command palette |
| [Yazi](https://yazi-rs.github.io/docs/quick-start/) | arrow and hjkl equivalence | beginner keys and expert aliases share actions |
| [Lazygit](https://lazygit.dev/docs/) | visible focused region, contextual hints, list/detail flow | focus marker, footer, and progressive details |
| [K9s](https://github.com/derailed/k9s) | in-product contextual help and quick navigation | `?` Help scoped to the active screen |
| [fzf](https://github.com/junegunn/fzf) | fuzzy narrowing instead of memorized exact commands | localized command discovery and local filters |
| [btop](https://github.com/aristocratos/btop) | readable density, reduced-color modes, optional mouse | compact operational data with keyboard completeness |

QuotaPilot does not copy any reference product's navigation tree, command
grammar, visual identity, or terminal composition.

## 2. Target users

### 2.1 First-time and occasional users

They need to see where they are, what is selected, what Enter will do, how to
go back, and how to ask for help. They must not need to read external
documentation or memorize keys before completing a workflow.

### 2.2 Daily keyboard users

They need low-latency movement, fuzzy command discovery, local filtering,
predictable focus, and minimal confirmation friction for safe actions.

### 2.3 Automation users

They continue to use the existing one-shot CLI. The TUI is never inserted into
an existing command or JSON pipeline.

### 2.4 Remote and constrained-terminal users

The interface must remain usable over SSH and near 80x24. Mouse and truecolor
are enhancements, not requirements.

## 3. Beginner interaction model

The first frame must visibly provide:

1. the current destination in the one-row header;
2. a selected item or focused action with both shape and color cues;
3. a contextual footer with three to six useful actions;
4. a visible destination list in standard/wide layouts, or a labeled menu
   affordance in compact layouts;
5. `? help` and `Ctrl+P commands` in the footer whenever space permits.

Beginner navigation uses:

```text
Down / Up           move selection
Left / Right        move between regions or open/back where indicated
Enter               open or activate the focused safe action
Esc                 close, cancel, or go back one level
Tab / Shift+Tab     next / previous focus region
```

Every screen must have a sensible initial focus. No screen may open with an
invisible focus target. Lists use a visible `>` or `▸` marker in addition to an
accent treatment. Buttons/actions render their actual result, such as
`[ Analyze ]`, `[ View details ]`, or `[ Approve & Execute ]`.

The footer teaches the current step rather than listing the entire keymap.
Examples:

```text
j/k select   Enter details   / filter   Esc back   ? help
```

```text
Tab select   Enter activate   Esc cancel   ? help
```

## 4. Expert interaction model

Expert keys accelerate the beginner model; they do not create a separate mode.

```text
j / Down       move down
k / Up         move up
h / Left       previous region / back where appropriate
l / Right      next region / open detail where appropriate
Enter          activate focused action
Esc            back / cancel / close overlay
Tab            next focus region
Shift+Tab      previous focus region
Ctrl+P         global command palette
Ctrl+D         details toggle outside text editing and confirmations
/              local filter only on supported screens
r              refresh or rerun where the footer advertises it
?              contextual help outside text input
q              quit only in normal navigation context
```

Target expert path:

```text
launch -> Ctrl+P -> type "route" -> Enter -> type task
       -> Ctrl+Enter -> review -> choose Dry Run or Execute
       -> explicit execution confirmation
```

`Ctrl+Enter` is the optional fast Analyze action in the Route editor. The
beginner path is `Tab` to `[ Analyze ]`, then `Enter`.

## 5. Information architecture

Required destinations, in task order:

```text
Overview
Route
Execute
Usage
Models
History
Settings
Doctor
```

The three candidate navigation models have different strengths:

| Model | Benefit | Limitation | Decision |
|---|---|---|---|
| persistent narrow navigation | immediate product map for beginners | consumes scarce compact width | use at 88+ columns |
| collapsed navigation | protects task content and actions | destination structure is one step away | use below 88 columns |
| command-palette-primary | fastest fuzzy expert path | insufficient as the only beginner path | always available as an accelerator |

The chosen architecture is therefore **adaptive narrow navigation plus the
command palette**:

- At 88 columns and above, a 12-14-cell text navigation rail remains visible.
  It makes the whole product discoverable without a large GUI-like sidebar.
- At 120 columns and above, the rail, main content, and an optional detail pane
  may coexist.
- Below 88 columns, the rail collapses. The header identifies the current
  destination, `h` / Left opens the destination overlay from the root content
  region, and `Ctrl+P` remains available.
- The command palette is always the fastest non-spatial route.

The navigation rail is a list, not a tree. It never contains nested settings or
provider-specific destinations.

## 6. Keybinding philosophy

1. Arrow keys are the canonical beginner bindings.
2. `hjkl` mirrors arrows only in navigation context.
3. Focused text controls own printable characters and editing keys.
4. Screen-specific bindings exist only when shown in the contextual footer or
   contextual help.
5. Global commands must not bypass required workflow steps.
6. A shortcut may disappear when invalid; an enabled-looking shortcut must
   work.
7. The same key has the same broad meaning across screens: `Esc` retreats,
   `Enter` activates, `/` filters locally, `Ctrl+P` discovers globally.

`Ctrl+D` is accepted as the details toggle in normal navigation. It is not a
priority binding over a focused text control because terminal editors commonly
use it for character deletion and Textual's input does so. Details remains
available from the command palette while text is focused.

`q` exits immediately only when there is no dirty form, pending approval, or
running execution. Otherwise it opens a safe confirmation. While text is
focused, `q` inserts text.

## 7. Focus model

There are exactly three interaction contexts.

### 7.1 Navigation context

Used by navigation, lists, read-only details, and action rows.

- One widget has input focus; one item inside a list may be selected.
- Focus is shown by a marker plus accent/reverse treatment.
- `Tab` and `Shift+Tab` traverse meaningful regions, not every static label.
- `h` / Left and `l` / Right move between adjacent regions when that motion is
  visible and logical.
- `Enter` opens the selected row or invokes the focused safe action.
- `Esc` closes detail first, then returns to the previous destination state.

### 7.2 Text input context

Used by Route task entry, palette query, local filters, and editable settings.

- Text behaves like a normal terminal editor; there is no INSERT mode.
- `h`, `j`, `k`, `l`, `q`, `/`, and `?` insert text.
- Arrow keys move the cursor or selection as the input widget normally defines.
- Route uses a soft-wrapped multi-line editor. Enter inserts a newline.
- `Tab` leaves the field for the next control; it does not insert a tab.
- `Esc` closes a transient search/palette or leaves the current form field
  without submitting it.
- `Ctrl+P` remains globally available.

### 7.3 Modal / confirmation context

Used by help, destination overlay, unsaved-change confirmation, and execution
approval.

- Input is confined to the topmost modal.
- `Esc` always selects the safe outcome: close or cancel.
- `Tab` / Shift+Tab and arrows move among modal actions.
- Execution approval never receives initial focus.
- `q`, `r`, `/`, and details shortcuts do not leak through the modal.

Focus returns to the widget that opened an overlay. If that widget no longer
exists, focus returns to the first meaningful action in the current screen.

## 8. Command palette

`Ctrl+P` opens a centered fuzzy command palette over the current view.

```text
                 + Command Palette --------------------------+
                 | > rou                                      |
                 |                                            |
                 | > Route a task                 Route       |
                 |   Open Routing settings        Settings    |
                 |   View routing profiles        Models      |
                 +--------------------------------------------+
                 Esc close   Up/Down select   Enter run
```

The palette contains commands, not raw CLI strings. It searches localized
titles and stable English keywords while retaining stable internal command IDs.
Initial empty results expose a short discovery set relevant to the current
screen.

Core command groups:

- destinations: Overview, Route, Execute, Usage, Models, History, Settings,
  Doctor;
- safe actions: Refresh quota, Toggle details, Open help;
- settings deep links: Budget reserve, Routing policy, Execution approval,
  Language, TUI theme;
- application: Quit.

Commands that require absent state are hidden or lead to the prerequisite
screen; they never silently fabricate that state. For example, `Execute`
navigates to the execution workflow but never approves or starts execution.
The palette never contains `Approve & Execute`.

Palette actions must pass through the same controller methods as visible
actions. There is no separate command-only implementation path.

## 9. Search and filter behavior

`Ctrl+P` is global command discovery. `/` is local collection filtering.

Local filter is supported on:

- Models: model ID, profile, freshness, routability;
- History: visible date/state/source fields only;
- Settings: category, label, and stable keywords.

When `/` is pressed in navigation context, a one-line filter appears at the top
of the local list and receives text focus. Results update as the user types.
`Esc` first clears a non-empty query, then closes an empty filter. Filtering
does not mutate data.

Route task entry and the command palette treat `/` as ordinary text.
Overview, Usage, Execute, and Doctor do not bind `/` unless a future collection
on that screen has a clear local filtering need.

Slash commands such as `/overview` and `/doctor` are **not part of Phase 9**.
They duplicate `Ctrl+P`, conflict with the clear local-filter meaning of `/`,
and introduce a second command grammar without shortening the intended flow.

## 10. Contextual help

`?` opens a modal whose content is generated from the active screen and
interaction context, not from a static wall of shortcuts.

```text
               + Help - Models -----------------------------+
               | Navigation                                  |
               |   j / Down       next model                 |
               |   k / Up         previous model             |
               |   Enter / Right  open details               |
               |   Esc / Left     back                       |
               |                                             |
               | Actions                                     |
               |   /              filter models              |
               |   r              refresh from snapshot      |
               |                                             |
               | Global                                      |
               |   Ctrl+P         command palette            |
               |   ?              this help                  |
               |   q              quit                       |
               +---------------------------------------------+
               Esc close
```

Help text uses the current language. It distinguishes unavailable actions and
explains the current focus when necessary. In text input context, `?` remains
text; users can leave the field with Esc or open Help from `Ctrl+P`.

## 11. Visual language

The TUI uses terminal-native hierarchy:

1. alignment and whitespace;
2. text weight/tone and concise labels;
3. one-cell separators;
4. a selection marker and restrained background/reverse treatment;
5. a border only for transient overlays or a safety-critical confirmation.

Rules:

- No ASCII logo or startup splash.
- No nested box explosion.
- No simulated GUI cards.
- No decorative charts or fake shadows.
- Use sentence case, short technical copy, and canonical identifiers.
- Use at most one strong visual emphasis per section.
- Prefer `Unknown`, `Stale`, `Unavailable`, and `Not authenticated` over icons.
- Unicode bars and sparklines are allowed only when a text value accompanies
  them and a plain-character fallback remains readable.

The interface uses the terminal's monospace font. It must not assume a
particular installed font or redistribute one.

## 12. Theme and color behavior

TUI theme choices are:

```text
System
Dark
Light
```

They are TUI presentation preferences and do not redesign or change the QML
GUI theme.

### System

Prefer terminal-default foreground/background and terminal ANSI palette where
the framework can preserve them reliably. Do not infer a light/dark terminal
background from unreliable environment heuristics. If terminal-default
surfaces cannot be rendered with readable contrast on the supported Textual
version, resolve to Dark and expose that resolved fallback in Settings and
Doctor rather than pretending detection succeeded.

### Dark and Light

Use explicit tested palettes. Dark uses deep navy-black and muted blue-gray
surfaces. Light uses quiet off-white surfaces and a darker navy/blue interaction
accent with sufficient contrast.

Semantic rules in every theme:

```text
interaction/focus/selection   restrained QuotaPilot navy/blue
SUCCESS                       green + "SUCCESS"
OVER                          amber + "OVER"
CRITICAL / ERROR              red + text label
UNKNOWN / Unavailable         gray + text label
STALE                         muted amber + "STALE"
ON_TRACK                      neutral text; not a green success wash
```

Green is reserved for explicit success/completion. Connected providers,
ordinary quotas, and fresh models use neutral text. A focused CRITICAL row
keeps its red `CRITICAL` label while gaining a separate blue focus marker.

The UI must remain understandable in monochrome, 16-color, 256-color, and
truecolor terminals. `NO_COLOR` disables nonessential chroma for the session;
selection marker, weight/reverse, and textual state remain.

## 13. Header and footer

### Header

The header is exactly one terminal row.

Wide/standard:

```text
QuotaPilot / Overview                         Codex - Connected
```

Compact:

```text
QuotaPilot / Overview
```

Provider state is omitted from the header when space is insufficient or when
the current view already gives it primary attention. It is never reduced to an
unlabeled color dot.

### Footer

The footer is one row and context-sensitive. It shows three to six actions,
ordered by immediate relevance. It may horizontally elide lower-priority hints
at compact widths but must retain Help and the safe exit/back action.

The footer is also mouse-clickable when mouse reporting is available. Mouse
labels call the same commands as their keys.

## 14. Overview

Overview answers:

1. how much quota remains;
2. whether usage is ahead or behind pace;
3. today's reasonable budget;
4. the current session's recommended model and effort, if a task was analyzed.

QuotaPilot cannot produce a task-specific recommendation without a task. Before
the session has a `RoutingRecommendation`, Suggested displays `Route a task`
rather than inventing a generic best model. A session recommendation is kept in
memory only and does not persist raw task text.

Default Overview wireframe (standard width):

```text
QuotaPilot / Overview                             Codex - Connected

 Overview    Weekly
 Route       ======================--------  68% used
 Execute
 Usage       32% remaining                 ON TRACK
 Models
 History     reset       4d 08h
 Settings    today       5.3%
 Doctor      pressure    .43

             Suggested

             > gpt-5.x - medium
               Sufficient capability at current quota pressure.

             Snapshot 2m ago - Fresh

--------------------------------------------------------------------
Enter route   r refresh   Ctrl+P commands   ? help   q quit
```

Only the binding quota pool is primary. Additional pools, source, exact reset
timestamp, raw pool ID, and profile diagnostics belong to Details.

On launch, Overview uses persisted/local values immediately, then starts one
eligible read-only provider refresh in the background. The values remain
visible and one local line changes to `Refreshing quota...`. A successful
refresh replaces them with the newly captured state. Failure retains the prior
values and labels them as persisted/stale as appropriate. `r` remains the
explicit manual refresh action.

## 15. Route

Route is advisory and never executes automatically.

Before analysis:

```text
QuotaPilot / Route                                Codex - Connected

 Overview    Route
 Route
 Execute     What are you working on?
 Usage
 Models      +----------------------------------------------------+
 History     | Add light theme support to QuotaPilot...           |
 Settings    |                                                    |
 Doctor      |                                                    |
             +----------------------------------------------------+

                                                   [ Analyze ]

             Task text stays in memory and is not added to history.

--------------------------------------------------------------------
Tab next   Ctrl+Enter analyze   Esc leave field   Ctrl+P commands
```

After analysis:

```text
QuotaPilot / Route                                Codex - Connected

 Overview    Route
 Route
 Execute     Recommended
 Usage
 Models      gpt-5.x - medium
 History
 Settings    Why
 Doctor        sufficient capability
               output is highly verifiable
               quota pressure is moderate

             Escalation
               model A - medium -> model B - high

             Task profile                              [ Details ]
               complexity .42   failure cost .31   class change

             > [ Dry Run ]          [ Execute ]

--------------------------------------------------------------------
h/l action   Enter select   Ctrl+D details   Esc edit   ? help
```

The default result exposes recommendation, concise reasoning, escalation, and a
three-field task summary. Full TaskProfile dimensions, scoring components,
provenance, and confidence appear in Details.

`Dry Run` transitions to Execute and builds a dry-run plan through the existing
execution service. `Execute` transitions to the real-plan review; neither
action starts an external process from Route.

## 16. Execute

Execution is deliberately stricter than Route. The Phase 6 execution service
remains authoritative.

Confirmation wireframe:

```text
QuotaPilot / Execute                              Codex - Connected

 Overview    Execute
 Route
 Execute     Model          gpt-5.x
 Usage       Effort         medium
 Models      Directory      ~/main/projects/QuotaPilot
 History
 Settings    Quota          ON TRACK - pressure .43
 Doctor      Approval       required
             Timeout        30m
             Attempts       3 maximum

             Escalation
               1  model A - medium
               2  model B - high

             WARNING: This action may modify files in this directory.

             > [ Cancel ]             [ Approve & Execute ]

--------------------------------------------------------------------
Tab select   Enter activate   Esc cancel   ? help
```

Safety rules:

- Working directory is always visible and is never horizontally hidden.
- Initial focus is `Cancel`, never `Approve & Execute`.
- Enter activates only the visibly focused action.
- The user must move focus to `Approve & Execute` before Enter can approve.
- Esc always cancels before execution starts.
- The palette cannot approve.
- The TUI requires an explicit approval gesture even when policy would not
  require a prompt; this is an additional UI gate, not a replacement for the
  service policy. `never_execute` still denies.
- Every materially changed escalation plan is shown in a new confirmation and
  requires a fresh approval gesture through the service approval callback.
- Retry/escalation counts, cancellation, revalidation, and cleanup remain Phase
  6 service/adapter responsibilities.
- Quitting during active execution requires a modal whose initial action is
  `Continue running`; cancellation must await service/adapter cleanup.

During execution, output is a bounded redacted tail. The header may show
`Executing` as text. Execution ownership is application-level so navigating to
another read-only screen does not silently cancel or orphan the task.

## 17. Usage

Usage keeps compact actual/expected summary values, then prioritizes a daily
end-of-day forecast from left to right:

```text
Actual      68.0%
Expected    61.5%
Delta       +6.5%
State       ON TRACK
Reset       4d 08h

Forecast — today's pace (projected day end)
Today       Fri         Sat         Sun
52%         76%         100%        124%
ON TRACK    OVER        CRITICAL    CRITICAL
```

The numbers above are illustrative. The shared forecast service derives real
values from today's persisted observations and the configured budget policy.
At 140 and 100 columns prefer one row. At 80 columns group into at most two
chronological rows, without horizontal scrolling. Normal cells show day,
projected percentage, and state; Ctrl+D reveals expected usage, delta,
remaining quota, date, and source. Unavailable and STALE are explicit.

At standard and compact widths, quota pools are a vertical list. Enter opens
one pool's technical details. Raw window metadata and provenance are Details
content. Horizontal scrolling is not permitted.

## 18. Models

Default list wireframe:

```text
QuotaPilot / Models                               Codex - Connected

 Overview    Models                                      Filter: none
 Route
 Execute     > gpt-5.x                         Fresh   Routable
 Usage         gpt-5.y                         Fresh   Routable
 Models        gpt-5.z                         Stale   Unavailable
 History       unknown                         Unknown Unavailable
 Settings
 Doctor

             4 models - 2 routable

--------------------------------------------------------------------
j/k select   Enter details   / filter   r reload   ? help
```

Model detail wireframe:

```text
QuotaPilot / Models / gpt-5.x                     Codex - Connected

 gpt-5.x

 Routable       yes
 Power          .78
 Cost           .55
 Latency        .31
 Efforts        low - medium - high

 Profile        local
 Freshness      Fresh
 Confidence     provisional

 Evidence       Versioned local routing profile
 Warnings       none

--------------------------------------------------------------------
Esc back   j/k scroll   Ctrl+D provenance   Ctrl+P commands   ? help
```

Wide mode may show list and detail together. Standard/compact mode replaces the
list with detail and uses Esc/Left to return. The list never becomes a wide
metrics table.

## 19. History

History has two explicit subviews:

```text
[ Usage history ]   [ Execution history ]
```

Usage history displays privacy-safe snapshot time, actual, expected, delta,
state, freshness/source, and details. At narrow widths a row becomes:

```text
2026-09-21 16:42
Actual 68%  Expected 62%  Delta +6%  ON TRACK
```

Phase 6 intentionally persists no execution audit. Until that core policy
changes, Execution history shows:

```text
Execution history is not stored.
QuotaPilot keeps task text and agent output in memory only.
```

The TUI must not synthesize execution rows from in-memory UI events or expose
raw task text.

## 20. Settings

Settings uses category list -> selected settings, never all fields at once:

```text
General
Budget
Routing
Execution
Models & Profiles
Integration
Appearance
```

Wide mode may show category and form side by side. Standard mode uses two
regions. Compact mode opens a category as a full view.

Settings behavior:

- `/` filters categories and labels.
- `Ctrl+P` can deep-link to a setting.
- Editable values use normal input/select controls.
- Validation occurs through authoritative strict configuration models.
- Save is explicit and atomic through the existing config writer.
- Dirty forms show `Unsaved changes` and intercept Esc/q/navigation with a safe
  discard confirmation.
- Language and TUI theme may apply live after a successful save. Other policy
  changes take effect on next launch, matching the current service-graph rule.
- The Phase 9.2B implementation applies saved appearance changes on next TUI
  launch as well. The existing screens compose localized labels at mount, so
  partially retranslated live state would be misleading.
- Canonical paths, model IDs, config keys, and command examples are not
  translated.

Appearance contains `System`, `English`, `日本語` for language and `System`,
`Dark`, `Light` for TUI theme.

## 21. Doctor

Doctor is a diagnostic interface over the existing Doctor service, not the CLI
renderer.

```text
QuotaPilot / Doctor                               Codex - Connected

 Doctor

 > PASS   Database
   PASS   Codex CLI
   PASS   Authentication
   WARN   Model profile freshness
   PASS   Packaging

 5 checks - 1 warning

--------------------------------------------------------------------
j/k select   Enter details   r rerun   ? help
```

Opening a check shows its status, privacy-safe detail, reason, and recommended
action. Default Doctor remains offline. A live provider check is a separately
labeled explicit action and never persists its diagnostic capture. Raw
exceptions, environment contents, authentication output, and credentials are
not shown.

## 22. Responsive behavior

Horizontal modes are based on terminal cells:

| Mode | Width | Composition |
|---|---:|---|
| Wide | `>= 120` | narrow nav + content + optional details |
| Standard | `88-119` | narrow nav + content; details replace content or overlay |
| Compact | `60-87` | single focused view; collapsed nav; secondary data hidden |
| Constrained | `< 60` | minimal resize guard for unsafe/complex views |

The 80-column compact-reference wireframe intentionally demonstrates the
boundary with collapsed navigation, as users may force compact mode or lose a
column to terminal behavior:

```text
QuotaPilot / Overview                                  Codex - Connected

Weekly
======================-------- 68% used

32% remaining                              ON TRACK
reset 4d 08h     today 5.3%     pressure .43

Suggested
> gpt-5.x - medium
  Sufficient capability at current quota pressure.

Snapshot 2m ago - Fresh







------------------------------------------------------------------------
Left menu   Enter route   r refresh   Ctrl+P commands   ? help   q quit
```

No primary workflow may require horizontal scrolling. Long values wrap or
elide with a visible ellipsis and open fully in detail. Paths show the tail when
necessary but reveal the full value on detail/focus; execution confirmation
must devote enough rows to show the full working directory by wrapping.

Vertical modes:

- `>= 30` rows: normal spacing and optional side details;
- `24-29` rows: compact spacing, one-row header/footer, scrolling body;
- `18-23` rows: secondary summaries collapse before actions;
- `< 18` rows: show a resize message for execution approval and other layouts
  that cannot be presented safely.

At 80x24 the header and footer consume one row each. The body scrolls, but
primary actions remain reachable through focus traversal and sticky action
rows where appropriate.

## 23. Localization and Japanese

The TUI uses the existing central preference:

```text
appearance.language = system | en | ja
```

System locale resolution matches GUI semantics: Japanese locales resolve to
Japanese; unsupported locales fall back to English. The TUI must not import Qt
to achieve this.

User-facing copy is looked up by stable message ID from packaged English and
Japanese catalogs. Strings must not be scattered through screens, widgets,
commands, and keymaps. Dynamic values are interpolated after translation.

Terminal layout rules:

- Measure rendered cell width, never Python `len()`.
- Use the framework/Rich `wcwidth` behavior for full-width Japanese,
  combining characters, and emoji.
- Do not manually pad translated labels to fixed code-point lengths.
- Prefer vertical label/value layout when Japanese expansion would compress a
  value below a useful width.
- Keep one-cell tolerance around aligned columns because ambiguous-width glyph
  rendering varies by terminal.
- Test English and Japanese at every acceptance size.
- Preserve model IDs, paths, config keys, enum values shown as technical data,
  and literal commands in canonical form.
- Japanese IME input and paste must be manually verified in the target
  terminals in addition to automated Unicode tests.

## 24. Mouse behavior

Mouse support is optional enhancement enabled when the terminal/framework
supports it:

- click to focus/select a navigation, list, or action item;
- click buttons and footer hints;
- scroll the region under the pointer;
- click a text field to position its cursor where supported.

Mouse actions call the same commands and safety gates as keyboard actions.
Hover alone communicates nothing essential. Right click, drag, double click,
and modifier-click are not required. Every workflow remains keyboard-complete.

## 25. Loading, error, UNKNOWN, and STALE states

The shell renders immediately. Initial local/database loading is quiet and
scoped to the affected region. Startup follows this order:

1. Render the shell and publish persisted/local state without waiting for the
   provider.
2. Inspect provider availability without starting authentication or another
   interactive provider flow.
3. If the provider is already authenticated, available, and its refresh path
   is known to be read-only, start exactly one non-blocking provider refresh.
4. On success, publish the refreshed status. On failure, retain the usable
   persisted report and expose its persisted, UNKNOWN, or STALE semantics plus
   an actionable status.

The automatic operation may read provider quota/model state and persist the
resulting coherent snapshot through the existing status service. It must not
start login, consume reset credit, execute a task, or mutate provider/account
configuration. If the current provider state cannot satisfy these conditions,
the refresh is skipped and the existing state remains authoritative. `r`
remains available for an explicit manual refresh; while the startup refresh is
active, another request is coalesced rather than run concurrently.

Examples:

```text
Loading persisted status...
Refreshing quota...
Analyzing task...
Running Doctor checks...
```

The prior useful content remains visible during refresh when safe. Exclusive
operations cancel or supersede older requests so a late response cannot
overwrite newer state.

First-class states:

```text
UNKNOWN
STALE
Unavailable
Not authenticated
Using persisted data
Loading
Error
Empty
```

UNKNOWN is never converted to `0`, `0%`, `safe`, or `unlimited`. STALE data
remains usable when the core permits it and always shows age/source. Errors are
compact and actionable:

```text
Provider unavailable

Using persisted snapshot from 18m ago - STALE

[ Retry ]   [ Open Doctor ]
```

Provider/raw exception text is not reflected. Local validation errors may name
the invalid field and expected value when safe.

## 26. Accessibility

- All primary workflows are keyboard-complete.
- Focus is visible through marker/weight/reverse as well as navy/blue.
- State is always textual and never color-only.
- Minimum contrast must be checked for Dark and Light palettes.
- System and `NO_COLOR` modes retain readable hierarchy without chroma.
- Motion is unnecessary; no animated transitions are required.
- Screen changes announce a text title and leave a stable reading order.
- Unicode symbols have text labels; essential meaning does not depend on a
  glyph rendering correctly.
- The footer is concise enough to be read repeatedly without becoming noise.
- Terminal screen-reader support varies; semantic text order, low redraw noise,
  and avoiding decorative output take priority over visual animation.

## 27. Anti-patterns

Phase 9 must not become:

- a terminal copy of QML geometry;
- a permanent wide SaaS sidebar;
- a card grid made from box characters;
- a Vim clone or modal editor;
- a generic terminal shell or slash-command language;
- a file manager;
- a second routing, budget, execution, provider, or persistence layer;
- an autonomous execution environment;
- an excuse to expose raw provider metadata or raw task history;
- an interface that requires truecolor, mouse, or 120 columns;
- an interface whose only discovery mechanism is memorized shortcuts.

Avoid large logos, retro-hacker styling, rainbow states, decorative borders,
excess badges, dense shortcut walls, wide tables, and full-screen loading for
ordinary service calls.

## 28. Acceptance criteria

The UX design is implemented correctly when:

1. `quotapilot tui` launches a persistent terminal application without changing
   existing one-shot commands.
2. A first-time user can reach and use all eight destinations with arrows,
   Enter, and Esc.
3. hjkl mirrors arrows in navigation context and inserts normally in text.
4. Route text entry behaves as a normal soft-wrapped editor with no INSERT
   mode.
5. Ctrl+P provides localized fuzzy discovery and never directly approves
   execution.
6. `/` filters only supported local collections; slash commands are absent.
7. Contextual help and footer hints match the current screen and focus context.
8. No footer shows more than six routine actions.
9. Execution shows full directory, quota, approval, limits, escalation, and a
   modification warning before approval.
10. Execution approval never has initial focus; Esc safely cancels; changed
    escalation plans require fresh visible approval.
11. Overview communicates remaining quota, pace state, today's budget, reset,
    and a task-specific suggestion or honest Route CTA.
12. Models and History use list/detail reflow without horizontal scrolling.
13. UNKNOWN, STALE, unavailable, authentication, loading, error, and empty
    states are explicit and actionable.
14. Persisted/local state renders before one eligible non-blocking startup
    refresh begins; refresh failure or an unsafe provider state preserves that
    state, and `r` remains available for manual refresh.
15. The UI remains responsive during provider, database, routing, execution,
    and Doctor operations.
16. Wide, standard, compact, 80x24, and vertically constrained behavior follows
    this specification.
17. English and Japanese render without clipped primary actions or manual
    code-point alignment.
18. System, Dark, Light, 16-color, and no-color behavior retains textual state
    and visible focus.
19. Mouse use is optional and invokes the same commands as keyboard use.
20. No task text, credentials, account identity, raw provider response, or
    unbounded execution output appears in history or logs.
21. The TUI calls core services directly and does not shell out to `quotapilot`.
22. The existing GUI remains unchanged in layout and behavior.
