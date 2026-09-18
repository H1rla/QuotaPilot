# Components

Only use components relevant to the product being built. The rules below are evidence-backed patterns, not required homepage content.

## Header

- **Anatomy:** brand anchor, desktop navigation, optional primary action; mobile replaces navigation with a toggle and fixed menu. **[OBSERVED]**
- **Geometry:** sticky top, 80px high, 80px horizontal padding desktop and 24px at ≤960px; 1px bottom rule. Brand media is 34px high. **[OBSERVED]**
- **Navigation:** 32px gap, 24px by ≤880px; plain text links. Primary action is 40px high with 4px radius, 8/16/8/10 padding, and an 18px icon. **[OBSERVED]**
- **States:** text links underline on hover. Primary action changes strong fill from `#201d1d` to `#302c2c`. Hide the primary action by 880px and all desktop navigation by 640px. **[OBSERVED]**
- **Mobile:** 40×40 transparent target; open menu is fixed below the 80px header, fills the viewport, and uses 20px vertical list padding with 20px link padding. **[OBSERVED, SOURCE-VERIFIED]**

## Announcement banner

- Inline row with 12px gap and 32px bottom margin. **[OBSERVED]**
- Badge uses strong fill, inverted text, weight 500, 4×8px padding, square corners, and `line-height:1`. **[OBSERVED]**
- Hide secondary platform/detail text progressively; below about 490px keep a short mobile link instead of wrapping the whole message. **[OBSERVED, SOURCE-VERIFIED]**

## Install selector

- **Anatomy:** contained tab list above one command panel. **[OBSERVED]**
- Tab list uses `surface-subtle`, 1px border except at the join, 6px top radii, 20px horizontal padding, 40px desktop gap / 32px compact gap. It renders 50–51px high. **[OBSERVED]**
- Tab text is weak by default. Selected tab becomes strong and receives a 2px bottom rule. `aria-selected` switches with the command. **[OBSERVED]**
- Panel uses the same surface, 1px border, 6px bottom radii, 16px padding, and 74px total height. **[OBSERVED]**
- At compact widths preserve one row with horizontal overflow; do not wrap labels. **[OBSERVED]**

## Command/copy field

- A command is a button inside a `pre`, not a faux input. Use 16/24px mono type, 8/16/8/8 padding, 16px internal gap, 4px radius, and a 16px copy icon. **[OBSERVED]**
- Highlight the package/product fragment with weight 500 and strong ink; keep shell syntax in normal muted ink. **[OBSERVED]**
- Hover uses `surface-subtle-hover`; copied state swaps copy/check icons. Panel content fades in 180ms when changing tabs. **[SOURCE-VERIFIED]**
- On mobile, truncate the command with ellipsis while preserving the copy action. **[OBSERVED]**

## Primary and secondary actions

- Primary: strong fill, inverted text, 500 weight, 4px radius, 40px typical height. Arrow/download icons remain small and utilitarian. **[OBSERVED]**
- Secondary: page fill, strong text, 1px subtle border, 4px radius. Hover changes only to subtle fill. **[OBSERVED]**
- Download-page action rows use 6×16px padding, 1px border, 4px radius, 200ms transition, and `scale(.98)` active feedback. **[SOURCE-VERIFIED]**
- Avoid pills, large color blocks, and shadowed CTA cards. **[INFERRED]**

## Feature item

- Use a flat vertical list, not separate cards. Each row is flex with a 12px gap and 16px bottom spacing. **[OBSERVED]**
- Lead with a muted syntax marker; use a 500-weight strong label and ordinary muted explanation. Prose line-height is 2.0 desktop / 1.8 compact. **[OBSERVED]**
- Keep the section CTA separate, approximately 40px below the list. **[OBSERVED]**

## Metric item

- Desktop/tablet use three equal flexible columns with 64px/48px gaps, preceded by a 40px indent and 48px top margin. **[OBSERVED]**
- Each item is illustration → 24px gap → label. The numeric value is strong and 500; descriptor is weak. Illustrations are thin, low-contrast line/dot/bar fields with no card background. **[OBSERVED]**
- Hide the visual metric group at ≤640px while keeping the evidence statement. **[OBSERVED]**

## FAQ accordion

- Full inner measure; no card or row borders. Questions are separated by 24px vertical rhythm. **[OBSERVED]**
- Question anatomy: 24px plus/minus icon, 16px gap, 500-weight label, 32px line box (30px compact). **[OBSERVED]**
- Expanded content is indented 40px, uses 2.0 line-height, ends with 32px spacing, and toggles `aria-expanded` plus/minus state. **[OBSERVED]**
- Keep one concise answer region under the question. Do not add colored accordions or rotating chevrons unless the product requires them. **[INFERRED]**

## Newsletter/conversion input

- One 66px field across the inner measure: subtle fill, 1px subtle border, 6px radius, 20px padding. The 40px primary button is absolutely inset 12px from the right. **[OBSERVED]**
- Focus changes fill to `feedback-subtle`, border to `surface-strong`, and adds a 3px `feedback` halo. **[OBSERVED]**
- At ≤480px, increase bottom padding to 80px and place the button left/right/bottom 20px, yielding a 124.5px field at the measured mobile viewport. **[OBSERVED]**

## Footer navigation

- Five equal cells in one row. Each link fills its cell with 32px vertical padding; adjacent cells use 1px vertical rules. **[OBSERVED]**
- Hover adds subtle fill and underline. Hide auxiliary counts below 640px. **[OBSERVED, SOURCE-VERIFIED]**
- At ≤400px, stack one cell per row and replace vertical rules with horizontal rules. **[OBSERVED]**

## Language selector

- Legal-row trigger is transparent, weak text, square, and uses a chevron; hover shifts toward normal text and underlines. **[OBSERVED]**
- Dropdown opens upward with an 8px gap, 160px width, maximum 420px height, 1px border, 3px radius, and the system's only routine shadow. Items are 13/19.5px with 10×12px padding and 150ms background transition. **[OBSERVED, SOURCE-VERIFIED]**
- Do not reuse the dropdown shadow for persistent content. **[INFERRED]**

