# Design tokens

## QuotaPilot app accent override

For the QuotaPilot desktop app, use the project-specific green accent below. This override applies before the marketing `feedback` color when implementing Phase 8.

| Token | Value | Use |
|---|---:|---|
| `accent` | `#7EE787` | active selection, safe primary action, link, limited chart emphasis |
| `accent-hover` | `#93ED9A` | hover state |
| `accent-pressed` | `#68D878` | pressed state |
| `accent-subtle` | `#122318` | selected-row/subtle active fill |
| `accent-focus` | `#254A31` | keyboard focus halo/outline support |
| `accent-on` | `#08110B` | text/icon on solid accent |

Do not replace warning/error/unknown/stale semantic colors with the accent. See `quotapilot-app-overrides.md`.


Use semantic names. Values below reflect the marketing pages, not the documentation or product app.

## Color

| Token | Light value | Dark value | Use |
|---|---:|---:|---|
| `page` | `hsl(0 20% 99%)` / observed `#fdfcfc` | `hsl(0 9% 7%)` | page and section background |
| `surface-subtle` | `hsl(0 8% 97%)` / observed `#f8f7f7` | `hsl(0 6% 10%)` | tabs, input, quiet hover regions |
| `surface-subtle-hover` | `hsl(0 8% 94%)` | `hsl(0 6% 15%)` | row and command hover |
| `surface-strong` | `hsl(0 5% 12%)` / observed `#201d1d` | `hsl(0 15% 94%)` | primary action, badges, strongest ink |
| `surface-strong-hover` | `hsl(0 5% 18%)` / observed `#302c2c` | `hsl(0 15% 97%)` | primary action hover |
| `feedback` | `hsl(62 84% 88%)` / observed `#f8fac7` | `hsl(62 100% 90%)` | focus halo and selection feedback |
| `feedback-subtle` | `hsl(64 74% 95%)` / observed `#fafce9` | `hsl(60 20% 8%)` | focused input fill |
| `text-strong` | `hsl(0 5% 12%)` / observed `#201d1d` | `hsl(0 15% 94%)` | headings, active tab, labels |
| `text` | `hsl(0 1% 39%)` / observed `#646262` | `hsl(0 4% 71%)` | body and code |
| `text-weak` | `hsl(0 1% 60%)` / observed `#9a9898` | `hsl(0 2% 49%)` | metadata and inactive tabs |
| `text-weaker` | `hsl(30 2% 81%)` / observed `#d0cfce` | `hsl(0 3% 28%)` | indices, quiet icons, separators |
| `border` | `hsl(30 2% 81%)` | `hsl(0 3% 28%)` | visible control border |
| `border-subtle` | `rgb(15 0 0 / 12%)` | `hsl(0 4% 23%)` | shell and section rules |
| `icon-muted` | `hsl(0 1% 55%)` | `hsl(10 3% 43%)` | nonessential icons |
| `text-inverted` | same as `page` | same as dark `page` | text on `surface-strong` |

**[OBSERVED]** RGB/hex values were read from Chrome computed styles. **[SOURCE-VERIFIED]** HSL definitions and dark-mode mappings match the public source.

Do not import the unrelated blue application token set exposed globally by the shared bundle. The marketing route overrides it with the warm neutral palette above. **[SOURCE-VERIFIED]**

## Spacing

Use this reduced working scale rather than copying every shared-framework token:

| Step | px | Typical use |
|---|---:|---|
| `1` | 4 | underline offset, tiny media-card inset |
| `2` | 8 | icon gap, compact padding, FAQ answer offset |
| `3` | 12 | inline groups, badge-to-copy gap |
| `4` | 16 | list-row gap, panel padding, baseline component rhythm |
| `5` | 20 | tab/input interior |
| `6` | 24 | mobile/tablet page gutter, heading-to-content, footer/legal gap |
| `8` | 32 | navigation gap, banner bottom, footer/legal spacing |
| `10` | 40 | command/tab gap on desktop, FAQ answer indent, CTA separation |
| `12` | 48 | tablet/mobile section padding, stacked download gaps |
| `16` | 64 | desktop section padding, desktop grid gap |
| `20` | 80 | desktop page/section inset |
| `24` | 96 | desktop hero vertical padding |

**[OBSERVED, INFERRED]** The source offers a broader 4px-oriented scale; this subset covers repeated marketing-site decisions. `56` and `72` occur as breakpoint interpolation/composition, not as core component steps.

## Geometry and elevation

- Outer shell: `max-width: 1080px`; rendered content box is 1078px inside its 1px border. **[OBSERVED]**
- Desktop inner measure: 918px (`1078 - 2 × 80`). **[OBSERVED]**
- Structural border: 1px; download hero uses 1px. The email source specifies 1px despite fractional platform rendering. **[OBSERVED, SOURCE-VERIFIED]**
- Radius: `0` structure, `4px` buttons/command, `6px` tabs/input, `8px` media card; generic shared dropdown is `3px`. **[OBSERVED, SOURCE-VERIFIED]**
- Standard action height: 40px. Tabs render 50–51px. Email input renders 66px desktop, 64.5px tablet, and 124.5px mobile because it reserves a second row for the button. **[OBSERVED]**
- Icons: copy 16px; header CTA 18px; row icons 20px; FAQ and model icons 24px; mobile menu target 40px. **[OBSERVED, SOURCE-VERIFIED]**
- Persistent shadow: none. Dropdown exception: `0 4px 12px rgb(0 0 0 / 10%)` light and 30% dark. **[OBSERVED, SOURCE-VERIFIED]**

## Breakpoints

| Breakpoint | Rule |
|---:|---|
| `65rem / 1040px` | remove outer shell border |
| `60rem / 960px` | page inset 80→24; section vertical padding 64→48; homepage base 16→15 |
| `55rem / 880px` | hide header primary CTA |
| `50rem / 800px` | stack download hero and label/content grids; broaden copy to full width |
| `40rem / 640px` | desktop nav→mobile menu; hide metric illustrations |
| `30rem / 480px` | compact hero; move newsletter action to its own row |
| `25rem / 400px` | footer cells stack one per row |

**[SOURCE-VERIFIED]** Actual 768px and 390px outcomes are recorded in [responsive.md](responsive.md).

