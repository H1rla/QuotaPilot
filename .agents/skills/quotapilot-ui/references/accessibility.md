# Accessibility

## Preserve

- Use semantic links for navigation/actions, buttons for tabs/copy/FAQ, a real email input, and `aria-selected`/`aria-expanded` state. **[OBSERVED]**
- Keep mobile controls at least 40×40px. The reference mobile menu and newsletter action meet this; text-only FAQ rows rely on a 30–60px line box. **[OBSERVED]**
- Keep command truncation visual only; expose the full command as the accessible name and copy value. **[INFERRED]**
- Respect `prefers-color-scheme` and swap both the palette and light/dark brand artwork when applicable. **[OBSERVED, SOURCE-VERIFIED]**

## Contrast guidance

- Measured light-theme approximations: `text-strong` on `page` ≈ 16.34:1 and `text` on `page` ≈ 5.92:1. These are suitable for normal text. **[INFERRED from observed colors]**
- `text-weak` on `page` ≈ 2.80:1 and `text-weaker` ≈ 1.52:1. Use them only for nonessential metadata, inactive state, or icon/separator detail; never for required instructions or primary labels. **[INFERRED from observed colors]**
- Do not convey tab selection only with the 2px underline; preserve the strong/weak text contrast and `aria-selected`. **[OBSERVED, INFERRED]**

## Improve when implementing

- Add an explicit `:focus-visible` treatment to links, buttons, tabs, FAQ questions, menu toggle, and copy actions. Use either a 2px strong outline with 2px offset or the existing yellow-green focus halo. **[INFERRED]**
- The inspected mobile menu visibly opened while its toggle still exposed `aria-expanded="false"`. New implementations must update it to `true` and connect the panel with `aria-controls`. **[OBSERVED]**
- Keep footer language options in a named listbox/menu pattern with keyboard navigation. The observed dropdown had buttons but no menu/listbox role on its container. **[OBSERVED]**
- Maintain visible labels or accessible names for icon-only copy/download actions. **[OBSERVED, INFERRED]**
- Honor `prefers-reduced-motion`; the visual system does not depend on motion, so transitions can be removed safely. **[INFERRED]**

## Unknowns

Per-glyph Japanese font fallback, complete keyboard order, screen-reader announcements for copied state, and disabled-state semantics were not exhaustively tested. Do not treat their absence from this document as approval to omit them. **[UNCERTAIN]**

