# Interactions

## State model

| Pattern | Default | Hover | Focus | Active/selected |
|---|---|---|---|---|
| text link | strong ink, no decoration | 1px underline, 4px offset | see focus guidance below | no persistent state |
| primary action | strong fill | strong-hover fill | reference page showed no distinct custom ring | download actions scale to `.98` |
| secondary action | page fill + 1px border | subtle fill | no distinct custom ring observed | optional `.98` on task actions |
| tab | weak ink + transparent 2px rule | no distinct change observed | empty `:focus-visible` rule in source | strong ink + strong 2px rule; `aria-selected=true` |
| command | transparent | subtle-hover fill | no distinct custom ring observed | copied icon swaps to check |
| FAQ | plus + strong label | no distinct color change | no distinct custom ring observed | minus + answer; `aria-expanded=true` |
| input | subtle surface | unchanged | feedback-subtle fill, strong 1px border, 3px feedback halo | typed text remains strong |
| footer cell | transparent | subtle fill + underline | no distinct custom ring observed | none |
| language item | transparent | surface fill | not reliably observed | selected item gets selected fill when token is available |

**[OBSERVED]** Hover and focus computed styles were sampled in Chrome. **[SOURCE-VERIFIED]** Download active transforms, copied icon swap, and exact transition declarations were confirmed in source.

## Timing

- Tab panel opacity: `180ms ease`. **[SOURCE-VERIFIED]**
- Download rows and copy-icon opacity: `150ms ease`. **[SOURCE-VERIFIED]**
- Download buttons: `200ms ease`. **[SOURCE-VERIFIED]**
- Dropdown trigger/items: `150ms ease`. **[OBSERVED, SOURCE-VERIFIED]**
- Most navigation, FAQ, and section interactions have no authored transition. Do not add broad 300–500ms motion. **[OBSERVED]**

## Behavior details

- Tab activation changes both `aria-selected` and command content; keep one row scrollable at compact widths. **[OBSERVED]**
- Command copy is the whole command target, not a tiny isolated icon. Keep the icon as confirmation and swap it to a check in copied state. **[OBSERVED, SOURCE-VERIFIED]**
- FAQ expansion swaps explicit plus/minus icons and reveals an indented answer. **[OBSERVED]**
- Mobile navigation is a fixed panel beginning below the 80px sticky header. Menu row hover uses the subtle surface. **[OBSERVED]**
- Language dropdown opens upward in the footer to avoid extending the document. **[OBSERVED]**
- Do not auto-submit forms or trigger downloads as a demonstration interaction. **[INFERRED]**

## Focus correction

The reference gives the email field a strong focus treatment but several button/link controls had no distinct computed focus ring during inspection. For new work, preserve the visual language while fixing this gap: use a 2px `surface-strong` outline with 2px offset, or the email-style 3px `feedback` halo where a contained control supports it. Apply only with `:focus-visible`. **[OBSERVED, INFERRED]**

