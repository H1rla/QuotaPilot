# QuotaPilot UI Design

Status: Normative UI design specification  
Design direction: OpenCode-inspired, modern, minimal, keyboard-first

## 1. Design goal

QuotaPilot should feel like a developer tool, not a generic SaaS dashboard.

The design language combines:

- OpenCode: terminal-first simplicity, command-driven navigation, sparse chrome
- Linear: quiet hierarchy, restrained density, low-noise navigation
- Raycast: keyboard-first commands, command palette, compact interactions
- Vercel/Grafana: metric clarity and operational status

The result should be:

```text
calm
technical
minimal
fast
keyboard-first
information-dense without visual noise
```

## 2. Product UI principle

The user should answer four questions immediately:

```text
How much quota remains?
Am I ahead or behind pace?
What can I safely use today?
What model/effort should I use?
```

Everything else is progressive disclosure.

## 3. Information hierarchy

### Level 1 — Actionable

Always visible on Overview:

- Remaining quota
- Reset time
- Budget state
- Today's budget
- Current recommendation when available

### Level 2 — Reasoning

Visible on expand/detail:

- pressure
- expected usage
- pace delta
- task profile
- routing explanation
- profile freshness/provenance

### Level 3 — Technical

Hidden unless explicitly opened:

- raw pool IDs
- metadata provenance details
- schema/version diagnostics
- provider-level details
- calibration evidence

## 4. Primary navigation

GUI default should avoid a visually heavy permanent sidebar.

Primary navigation:

```text
Ctrl+P — command palette
```

Optional compact sidebar may be user-configurable.

Primary destinations:

```text
Overview
Usage
Models
Route
Execute
History
Settings
Doctor
```

## 5. Command palette

`Ctrl+P` opens a centered command palette.

Example:

```text
> rou

Route a task
Change routing policy
Open routing settings
```

Commands should be searchable by fuzzy text.

Palette actions may include:

- Overview
- Refresh quota
- Route a task
- Execute task
- Usage history
- Models
- Settings
- Doctor
- Toggle details
- Change routing policy

## 6. Keyboard model

Recommended defaults:

```text
Ctrl+P   Command palette
Ctrl+R   Refresh
Ctrl+D   Toggle details
Ctrl+,   Settings
Esc      Back / Cancel
Enter    Select / Confirm
↑ ↓      Navigate
/        Command entry in TUI
```

GUI shortcuts should mirror TUI semantics where practical.

## 7. Visual style

### Background

Use terminal-like dark surfaces.

Conceptual palette:

```text
window          #0B0D10
surface         #111419
surface-raised  #15191F
border          #242A31
text-primary    #F2F4F7
text-secondary  #A5ADB8
text-muted      #68717D
```

Exact values may be tuned.

### Semantic colors

Keep semantic color usage minimal.

```text
VERY_UNDER   cool cyan/blue
UNDER        muted cyan
ON_TRACK     neutral
OVER         amber
CRITICAL     red
SUCCESS      green
UNKNOWN      gray
STALE        muted amber
ERROR        red
```

Do not color ordinary percentages merely because they are numerically high.

Semantic meaning controls color.

## 8. Typography

Use a modern sans UI font with optional monospace for technical values.

Recommended hierarchy:

```text
Page title        24–28 px / medium
Section title     15–17 px / medium
Metric            28–40 px / semibold
Body              13–15 px
Caption            11–12 px
Technical value   monospace
```

Do not use excessive font sizes.

## 9. Spacing

Base unit:

```text
4 px
```

Common spacing:

```text
4
8
12
16
24
32
```

Avoid oversized 48–64 px whitespace common in marketing dashboards.

This is a developer tool.

## 10. Borders and cards

Avoid card explosion.

Use:

- spacing
- alignment
- typography
- subtle separators

before adding bordered cards.

Cards are appropriate only for truly distinct interactive units.

Corner radius should be restrained:

```text
6–10 px
```

Avoid large pill-shaped dashboard components everywhere.

## 11. Overview layout

The default GUI screen should resemble:

```text
QuotaPilot                                      Codex ● Live

Weekly
████████████████████████░░░░░░░░░     67%

33% remaining                           reset 4d 18h

OVER · pressure .70


Usage

100 ┤
 75 ┤                          ╭──── actual
 50 ┤               ╭──────────╯
 25 ┤ · · · · · · · · · · · · · · expected
  0 └──────────────────────────────────────
     Mon       Tue       Wed       Thu


Today                 Models                 Profiles
3.8%                  3 / 6                  Fresh


Suggested
Terra · high

Sufficient capability with lower quota cost.
Usage is currently ahead of expected pace.
```

The GUI should not start with six equally weighted KPI cards.

## 12. Overview priority

Primary emphasis:

```text
remaining
state
today budget
reset
```

Secondary:

```text
pressure
models routable
profile freshness
```

Technical metadata remains hidden.

## 13. Usage view

Purpose: show projected cumulative quota usage at the end of each remaining
local day, from left to right. The primary visualization is the shared daily
forecast strip, with at most seven points and no point beyond reset.

Summary:

```text
Actual
Expected
Delta
State
Reset
```

Each normal cell contains only day, projected percentage, and the existing
BudgetState label. Details may add expected usage, delta, remaining quota, full
date, and source/freshness. When evidence is insufficient or timing is unknown,
show an explicit unavailable reason. Never clamp displayed percentages at 100%.
At 1100 × 720 use one row; at narrower widths tighten spacing, then use a
controlled two-row wrap. History retains persisted observations.

## 14. Models view

Use a compact table/list.

Columns:

```text
Model
Power
Cost
Latency
Effort
Profile
```

Example:

```text
Luna      .55   .30   .18   high      Fresh
Terra     .75   .55   .34   high      Fresh
Sol      1.00  1.00   .82   high      Fresh
New       —     —     —      —         Unknown
```

Selecting a model opens detail.

Detail should show:

- exact model ID
- selectable/routable
- power/cost/latency
- supported efforts
- effort order
- source
- confidence
- verified date
- stale status
- evidence

## 15. Route view

The main interaction is one large task input.

```text
What are you working on?

[ Refactor authentication and remove duplicated
  session validation                              ]

                                              Analyze
```

After analysis:

```text
Task profile

Complexity       ███████░░░ .72
Ambiguity        ████░░░░░░ .41
Failure cost     ██████░░░░ .63
Verifiability    ███████░░░ .74


Recommended

Terra · high

✓ sufficient capability
✓ output is highly verifiable
✓ quota currently ahead of pace

Escalation
Terra high → Sol medium → Sol high
```

Actions:

```text
Dry Run
Execute
```

## 16. Advanced task editing

Task-profile sliders/fields should be hidden under:

```text
Advanced
```

Default users should not need to manually tune six dimensions.

Advanced view may allow explicit overrides.

## 17. Execute view

Execution must feel deliberately stricter than Route.

Display:

```text
Execution Plan

Model             Terra
Effort            high
Directory         ~/project/foo

Quota             OVER · .70
Approval          required
Timeout           30 min
Attempts          3

Escalation
1 Terra · high
2 Sol · medium
3 Sol · high

This action may modify files in the working directory.

Cancel                      Approve & Execute
```

Never hide working directory.

Never make execution a single accidental click from task entry.

## 18. Confirmation interaction

Real execution should use a distinct confirmation step.

Keyboard:

```text
Esc     cancel
Enter   approve
```

For high-risk states, require explicit focus/selection before Enter approval.

## 19. History view

Separate:

```text
Usage history
Execution history
```

Routing/execution history should use privacy-safe metadata.

Example:

```text
16:42  repository-change  Terra/high  SUCCESS  pressure .70
15:18  debugging          Sol/medium  FAILED   pressure .35
```

Do not display raw task text unless future opt-in storage exists.

## 20. Settings view

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

### Budget

- reserve
- timezone
- stale threshold
- weekday weighting

### Routing

- routing policy
- unknown quota pressure
- latency preference

### Execution

- approval mode
- max attempts
- retry count
- timeout

### Models & Profiles

- profile locations
- freshness
- metadata source

## 21. Settings search

Settings must be searchable.

Command palette:

```text
> reserve
```

should navigate directly to the reserve setting.

## 22. Details mode

Use one global details toggle.

Concept:

```text
Ctrl+D
```

Normal:

```text
Terra · high
OVER · .70
```

Details:

```text
Terra · high

power        .75
cost         .55
latency      .35
profile      local-profile
confidence   provisional
verified     2026-09-18

task difficulty  .71
quota pressure   .70
utility          .64
```

This avoids separate novice/expert UIs.

## 23. Loading states

Use quiet inline loading.

Preferred:

```text
Refreshing quota…
Analyzing task…
Building execution plan…
```

Avoid full-screen spinners for short actions.

Do not shift layout excessively while loading.

## 24. UNKNOWN state

UNKNOWN is a first-class visual state.

Display:

```text
Unavailable
Unknown
Insufficient data
```

Do not display:

```text
0%
Safe
Unlimited
```

when data is unknown.

## 25. STALE state

Stale data should remain usable but visibly labeled.

Example:

```text
Snapshot 18m ago · STALE
```

Use muted warning color, not critical red unless it blocks execution.

## 26. Error state

Errors should be compact and actionable.

Example:

```text
Provider unavailable

Showing last persisted snapshot from 18 minutes ago.

Retry
Doctor
```

Avoid stack traces in normal GUI.

## 27. Empty state

Example Models empty state:

```text
No routable models

Capability metadata is missing or stale.

Open Models
Run Doctor
```

Always provide next action.

## 28. GUI framework

Preferred stack:

```text
PySide6
Qt Quick / QML
```

Reason:

- existing Python core can be called directly,
- no Python subprocess bridge required,
- strong desktop support,
- QML is appropriate for modern dashboard UI,
- clean separation between ViewModel and presentation.

## 29. GUI architecture

```text
QuotaPilot services
      ↓
GUI ViewModels
      ↓
QML
```

Forbidden:

```text
GUI
→ subprocess("quotapilot status")
```

GUI must call existing services directly.

## 30. GUI package

Suggested:

```text
src/quotapilot/gui/
├── __init__.py
├── app.py
├── controllers/
├── viewmodels/
├── resources/
└── qml/
    ├── Main.qml
    ├── Overview.qml
    ├── Usage.qml
    ├── Models.qml
    ├── Route.qml
    ├── Execute.qml
    ├── History.qml
    ├── Settings.qml
    └── components/
```

Exact organization may be refined.

## 31. Shared components

Suggested reusable QML components:

```text
Metric.qml
StateBadge.qml
ProgressBar.qml
Section.qml
CommandPalette.qml
KeyHint.qml
EmptyState.qml
ErrorState.qml
ModelRow.qml
ProfileBadge.qml
```

Avoid giant monolithic QML files.

## 32. ViewModels

GUI ViewModels should expose UI-ready state but not business logic.

Examples:

```text
OverviewViewModel
UsageViewModel
ModelsViewModel
RouteViewModel
ExecuteViewModel
HistoryViewModel
SettingsViewModel
```

ViewModel may format display values where appropriate.

Budget/routing calculations remain in services/core.

## 33. Async behavior

GUI must remain responsive during:

- provider refresh
- routing
- execution
- database access

Do not block the Qt main thread with synchronous provider calls.

Use appropriate async/worker integration.

## 34. Command palette

The command palette is a first-class navigation surface.

GUI shortcut:

```text
Ctrl+P
```

TUI should use an equivalent command surface.

Palette supports fuzzy filtering.

## 35. Sidebar

Default design should minimize permanent chrome.

Two acceptable modes:

```text
sidebar hidden/compact by default
command palette primary
```

or:

```text
narrow icon/text sidebar
```

Do not use a large 240px SaaS navigation rail unless testing shows it is necessary.

## 36. Window sizing

Default desktop window should fit laptop displays.

Suggested initial target:

```text
1100 × 720
```

Minimum should remain usable around:

```text
900 × 600
```

Do not optimize only for large desktop monitors.

## 37. Responsive layout

When width decreases:

1. secondary metrics collapse,
2. the forecast strip tightens or wraps into two chronological rows,
3. optional details hide,
4. primary actions remain accessible.

Do not horizontally scroll the main dashboard.

Tables may use controlled horizontal behavior where unavoidable.

## 38. TUI direction

If a full-screen TUI is implemented, it should mirror GUI information architecture rather than create a separate product.

Default TUI:

```text
QuotaPilot                                   Codex ● live

weekly
████████████████████████░░░░ 67%

33% remaining                     reset 4d18h
OVER                              pressure .70


usage
100 ┤
 75 ┤                       ╭──── actual
 50 ┤             ╭─────────╯
 25 ┤ · · · · · · · · · · · · expected
  0 └───────────────────────────────────


today 3.8%     models 3/6     profiles fresh


suggestion
Terra · high

────────────────────────────────────────────
/ command                              ctrl+p
```

## 39. TUI command model

OpenCode-inspired commands:

```text
/overview
/usage
/models
/route
/execute
/history
/refresh
/details
/settings
/doctor
/help
```

`Ctrl+P` should open command palette if the TUI framework permits.

## 40. Mini mode

Optional compact terminal mode:

```bash
quotapilot mini
```

Concept:

```text
QP 33% left · OVER .70 · today 3.8% · reset 4d18h

>
```

Useful for SSH/small terminals.

Not a Phase 8 GUI blocker.

## 41. Accessibility

- do not rely on color alone,
- maintain readable contrast,
- keyboard navigation complete,
- focus visible,
- status labels textual,
- animations subtle and optional.

## 42. Motion

Use minimal motion.

Appropriate:

- 120–180ms fades
- subtle panel transitions
- progress updates

Avoid:

- bouncing elements
- decorative loading animation
- large parallax effects

## 43. Iconography

Use simple outline icons sparingly.

Primary interfaces should still work with text.

Do not add icons to every metric.

## 44. Branding

Product name:

```text
QuotaPilot
```

Visual mark should be simple and geometric.

Do not use cliché AI sparkle/brain imagery.

A future logo may use:

```text
Q
gauge
trajectory
quota arc
```

in an abstract minimal form.

## 45. GUI launch

Preferred commands:

```bash
quotapilot gui
```

and eventually a desktop launcher.

Running plain:

```bash
quotapilot
```

may remain CLI-oriented unless a separate product decision changes it.

Do not break established CLI scripts.

## 46. Waybar relationship

Waybar is glanceable status.

Click action may launch:

```text
QuotaPilot GUI → Overview
```

if desktop integration supports it.

Waybar should not duplicate the full UI.

## 47. Design tokens

UI implementation should centralize:

```text
colors
spacing
radius
font sizes
animation duration
```

Do not scatter literal styling across QML.

## 48. Theme

Initial required theme:

```text
Dark
```

Optional:

```text
System
Light
```

may come later.

Do not delay first GUI for complete theming.

## 49. Product tone

UI text should be:

```text
short
technical
calm
non-judgmental
actionable
```

Examples:

Good:

```text
Usage is 11% ahead of pace.
```

Avoid:

```text
You're using way too much quota!
```

## 50. UI acceptance criteria

UI design implementation is correct when:

1. Overview communicates remaining/state/budget/reset immediately.
2. GUI uses existing services directly.
3. No business logic is duplicated in QML.
4. Command palette works.
5. Keyboard navigation works.
6. UNKNOWN and STALE are first-class states.
7. Route explains recommendation.
8. Execute always shows plan before real execution.
9. Models shows provenance/freshness.
10. Settings edits safe supported configuration.
11. Human-readable hierarchy works without color.
12. GUI remains responsive during async operations.
13. Window works on laptop-scale displays.
14. No raw account/private metadata is exposed.
15. Visual design remains minimal and developer-oriented.

## 51. Localization and provider status

The GUI supports System, English, and Japanese. Japanese labels may expand;
controls must reflow or elide technical values without clipping primary
actions. Prefer a Japanese-capable system font fallback and retain canonical
model/provider IDs, paths, config keys, and CLI commands.

Provider status is secondary on Overview. Use one compact ruled section with
connection/authentication, last refresh, and data freshness. Connected is a
small success state, not a dominant green card. Unavailable, Not authenticated,
Unknown, and persisted STALE data retain explicit text and semantic colors.
