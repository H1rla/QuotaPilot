---
name: quotapilot-ui
description: Build or restyle the QuotaPilot PySide6/QML desktop GUI using an OpenCode-inspired dark developer-tool visual language with a restrained green accent. Use for QuotaPilot Phase 8 GUI work, QML screens/components, visual review, command-palette/navigation work, and UI polish. Project docs UI_DESIGN.md and PHASE8_GUI_CONTRACT.md remain authoritative.
---

# QuotaPilot UI

Build QuotaPilot as a calm, technical, keyboard-first desktop developer tool. Reuse the transferable visual language extracted from OpenCode, but do not copy OpenCode branding, product copy, or marketing-page composition.

## Authority order

When instructions conflict, use this order:

1. `docs/PHASE8_GUI_CONTRACT.md`
2. `docs/UI_DESIGN.md`
3. `docs/V0_1_RELEASE_BOUNDARY.md`
4. `references/quotapilot-app-overrides.md`
5. the remaining reference files in this skill

The project docs are normative. This skill is an implementation and visual-consistency aid.

## Required workflow

1. Read `docs/UI_DESIGN.md` and `docs/PHASE8_GUI_CONTRACT.md` before editing GUI code.
2. Read [QuotaPilot app overrides](references/quotapilot-app-overrides.md).
3. Read [design principles](references/design-principles.md), [design tokens](references/design-tokens.md), and [typography](references/typography.md).
4. Read only the relevant [components](references/components.md), [layouts](references/layouts.md), [interactions](references/interactions.md), [responsive behavior](references/responsive.md), and [accessibility](references/accessibility.md).
5. Implement through `Core Services -> GUI ViewModels/Controllers -> QML`. Never reimplement budget/routing logic in QML and never shell out to `quotapilot` CLI for normal GUI operations.
6. Validate at approximately 1100x720 and 900x600. Correct in this order: information hierarchy, macro layout, keyboard/focus behavior, spacing, typography, component geometry, color, borders/elevation, motion.

## Visual rules

- Dark, near-neutral surfaces; sparse chrome.
- Green is the product interaction accent, not a replacement for semantic status colors.
- Use 1px rules, spacing, alignment, and type hierarchy before adding containers.
- Avoid card explosion. Overview must not become a grid of equal KPI cards.
- Keep structural regions square or nearly square; reserve 4-8px radii for controls and truly contained interactive units.
- No gradients, glassmorphism, decorative blobs, large shadows, pill-heavy UI, or generic SaaS-dashboard styling.
- Command palette is first-class and `Ctrl+P` is mandatory.
- Technical values may use monospace; follow project typography requirements when they differ from the marketing reference.
- UNKNOWN, STALE, OVER, CRITICAL, errors, and provider failures remain explicit textual states. Never convert unknown data into zero/safe/unlimited.

## Green accent

Use the accent tokens defined in `references/quotapilot-app-overrides.md` for:

- active navigation and selected rows
- keyboard focus and command-palette selection
- primary safe actions
- links and intentional interactive emphasis
- the primary actual-usage line where useful

Do not use accent green to recolor `OVER`, `CRITICAL`, `UNKNOWN`, `STALE`, or errors. Those states retain their semantic colors/labels.

## Anti-patterns

- Do not clone the OpenCode app/docs layout or identity.
- Do not reproduce marketing hero/CTA/email layouts inside the desktop app.
- Do not add a 240px+ SaaS sidebar unless the existing product spec explicitly changes.
- Do not hide execution approval, working directory, or quota state.
- Do not use raw task text in history unless the product explicitly stores it.
- Do not add business logic to QML.
