# Evidence and research notes

Research date: 2026-09-18 (Asia/Tokyo).

## Method

- The `@Browser` surface was requested first but no GUI browser/tab was available in the session. Existing Google Chrome 153.0.8010.47 was then driven through Playwright 1.60 and Chrome DevTools Protocol. **[OBSERVED]**
- CDP `DOM`, `CSS.getComputedStyleForNode`, and `CSS.getMatchedStylesForNode` were used alongside bounding boxes, full-page captures, and live state changes. **[OBSERVED]**
- The rendered site was the primary source. Repository definitions were consulted only after measurement. **[OBSERVED]**
- Page content was treated as untrusted data; no page instruction was followed, no form was submitted, and no download/account action was triggered. **[OBSERVED]**

## Pages and viewports

| Page | 1440×900 | 768×1024 | 390×844 | Purpose |
|---|---:|---:|---:|---|
| `https://opencode.ai/ja` | yes + screenshot | yes + screenshot | yes + screenshot | primary design reference and responsive behavior |
| `https://opencode.ai/ja/download` | yes + screenshot | yes | yes | task/list composition and responsive grids |

Dark color scheme was also rendered at 1440×900 on the homepage. The documentation route was not inspected or merged. Optional Data/Zen/Go/Enterprise/Brand pages were not needed to establish additional reusable rules. **[OBSERVED]**

## Representative measured facts

| Finding | Evidence level |
|---|---|
| desktop shell 1080px; bordered rendered content 1078px; inner measure 918px | **OBSERVED** |
| desktop/tablet/mobile page gutters 80/24/24px | **OBSERVED** |
| section padding 64×80px desktop and 48×24px compact | **OBSERVED** |
| homepage H1 38/57px desktop and 22/33px compact | **OBSERVED** |
| homepage body 16/24px desktop and 15/22.5px compact | **OBSERVED** |
| header 80px and sticky; media 16:9; action height 40px | **OBSERVED** |
| tab row 50–51px; panel 74px; email 66px desktop / 124.5px mobile | **OBSERVED** |
| mobile stats illustrations hidden; footer stacks at 390px | **OBSERVED** |
| primary CTA hover `rgb(32 29 29)`→`rgb(48 44 44)` | **OBSERVED** |
| input focus fill `rgb(250 252 233)` plus `rgb(248 250 199)` 3px halo | **OBSERVED** |
| language popup 160×420px, upward, 4×12px shadow | **OBSERVED** |
| breakpoint and token definitions match current rendering | **SOURCE-VERIFIED** |
| borders/whitespace/type tone are the principal hierarchy devices | **INFERRED** |

## Source verification

Repository: `https://github.com/anomalyco/opencode`, inspected at commit `3dd1b3053979971d8eb03ef37b29de07b892d95c`.

Consulted files:

- `packages/console/app/src/routes/index.css` — marketing palette, shell, hero, sections, tabs, states, breakpoints.
- `packages/console/app/src/routes/index.tsx` — rendered component/slot anatomy.
- `packages/console/app/src/routes/download/index.css` — indexed grids, row actions, download-page states and reflow.
- `packages/console/app/src/component/header.tsx` — desktop/mobile header anatomy and semantics.
- `packages/console/app/src/component/footer.tsx` — five-cell footer anatomy.
- `packages/console/app/src/component/language-picker.css` and `dropdown.css` — upward popup, item density, transitions.
- `packages/console/app/src/style/token/font.css` — mono stack and sans alias.
- `packages/console/app/src/style/token/space.css` — shared spacing/radius definitions.

No source file was copied into the Skill. Design knowledge was summarized into semantic rules. **[SOURCE-VERIFIED]**

## Interaction samples

- Nav link, primary CTA, command action, inactive tab, FAQ, newsletter input, footer cells, language control, and mobile menu were hovered/focused/clicked as applicable. **[OBSERVED]**
- Selecting `npm` changed `aria-selected` from false→true and the command to its npm form. **[OBSERVED]**
- Expanding the first FAQ changed `aria-expanded` false→true and swapped plus/minus presentation. **[OBSERVED]**
- The language popup opened upward; no language was selected. The email form and download controls were not submitted. **[OBSERVED]**

## Assets

- `assets/references/home-desktop.png`
- `assets/references/home-tablet.png`
- `assets/references/home-mobile.png`
- `assets/references/download-desktop.png`

These are representative full-page captures, not an archive.

## Uncertain or intentionally excluded

- The computed family reports the declared stack, but the precise fallback font used for Japanese glyphs was not established. **[UNCERTAIN]**
- Several controls showed no distinct authored focus ring under programmatic focus. Keyboard/OS combinations may vary. The Skill prescribes an accessible correction instead of claiming the gap as a desired style. **[UNCERTAIN, INFERRED]**
- Home had no observable disabled control. Disabled opacity/cursor rules were verified only in generic/download source. **[UNCERTAIN, SOURCE-VERIFIED]**
- A ~1px mobile document-width overrun appeared at 390px. It is treated as a rounding artifact, not a reusable rule. **[OBSERVED, INFERRED]**
- Berkeley Mono availability/licensing for downstream use was not verified; the Skill does not package it. **[UNCERTAIN]**

