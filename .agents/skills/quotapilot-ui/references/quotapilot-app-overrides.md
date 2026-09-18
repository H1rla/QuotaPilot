# QuotaPilot desktop-app overrides

This file adapts the extracted OpenCode visual language for QuotaPilot's PySide6/QML desktop application. It overrides marketing-only assumptions in the other reference files.

## 1. Product context

QuotaPilot is a local-first quota-aware developer tool, not a marketing website.

Primary screen goals:

- remaining quota
- budget state
- today's budget
- reset time
- model/effort recommendation

Secondary information is progressively disclosed.

## 2. Accent system — green

Green is the QuotaPilot interaction/brand accent.

```text
accent              #7EE787
accent-hover        #93ED9A
accent-pressed      #68D878
accent-subtle       #122318
accent-focus        #254A31
accent-on           #08110B
```

Use accent for selection, keyboard focus, current navigation, safe primary actions, links, and limited chart emphasis.

Never let the accent overwrite semantic state meaning:

```text
OVER       amber
CRITICAL   red
ERROR      red
UNKNOWN    gray
STALE      muted amber
```

`ON_TRACK` does not need to become a large green badge. Prefer neutral text with a small accent/semantic indicator when useful.

## 3. Dark surface tokens

Prefer the QuotaPilot normative palette from `docs/UI_DESIGN.md`:

```text
window          #0B0D10
surface         #111419
surface-raised  #15191F
border          #242A31
text-primary    #F2F4F7
text-secondary  #A5ADB8
text-muted      #68717D
```

The extracted marketing light theme is reference material only; Phase 8 requires dark first.

## 4. Layout adaptation

Do not reuse marketing shell/hero/CTA composition.

Desktop app composition should favor:

```text
compact top bar / project-provider context
optional narrow navigation rail
main content
optional contextual detail region
command palette overlay
```

Command palette remains primary navigation. A narrow icon/text sidebar is acceptable but should remain low-noise.

At 1100x720, keep all Level-1 Overview information visible without scrolling when practical. Around 900x600, collapse secondary details before primary actions.

## 5. Containers

Use a card only when the unit is independently interactive or semantically distinct.

Preferred hierarchy:

1. whitespace
2. typography
3. 1px separator
4. subtle surface change
5. bordered container only when needed

Avoid six equally weighted KPI cards.

## 6. Typography

Project documentation wins over marketing references.

- Use the app's chosen modern UI font for body/navigation if available.
- Use monospace deliberately for model IDs, percentages, timestamps, quota values, command text, key hints, and technical details.
- A mono-heavy treatment is allowed if it remains legible, but do not force every prose paragraph into terminal styling solely because the marketing reference does.

## 7. Interaction model

Required shortcuts:

```text
Ctrl+P  command palette
Ctrl+R  refresh
Ctrl+D  toggle details
Ctrl+,  settings
Esc     back/cancel
Enter   select/confirm
```

Focus must be clearly visible. Prefer a 2px green accent outline/halo with restrained opacity rather than large glow.

## 8. Motion

Keep state-driven motion within roughly 120-180ms for fades/selection/panel changes. Avoid decorative animation.

## 9. Overview visual target

The Overview should read as one coherent technical surface rather than a dashboard-card mosaic.

A good order is:

```text
page title / provider freshness
remaining | reset | state | today's budget
secondary inline metrics
actual vs expected pace visualization
current recommendation + concise explanation
```

Recent activity/provider diagnostics are secondary and should not compete with the four primary questions.
