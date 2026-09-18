# Typography

## Family

Use one mono family across navigation, prose, headings, controls, metrics, and code:

`"Berkeley Mono", "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`

The source maps its nominal sans token back to the mono token. Code differs through syntax, containment, color, and `white-space`, not through a second font. **[OBSERVED, SOURCE-VERIFIED]**

Berkeley Mono may not be available or licensed in a downstream project. Prefer IBM Plex Mono or a high-quality mono already licensed by that project; do not redistribute Berkeley Mono. **[UNCERTAIN]**

## Semantic roles

| Role | Desktop | ≤960px / mobile | Weight | Color | Notes |
|---|---|---|---:|---|---|
| Marketing H1 | 38px / 57px | 22px / 33px | 700 | `text-strong` | no tracking or transform |
| Download H1 | 24px / 36px | 24px / 36px | 700 | `text-strong` | smaller, task-oriented page |
| Section H3 | 16px / 24px | 16px / 24px | 700 | `text-strong` | section labels stay compact |
| Body | 16px / 24px | homepage 15px / 22.5px | 400 | `text` | default UI copy |
| Prose | 16px / 32px | 15px / 27px | 400 | `text` | 200%→180% line-height |
| Navigation | 16px / 24px | 15px / 22.5px | 400 | `text-strong` | underline only on hover |
| Button/label | 16px / 24–32px | 15px / 22.5–30px | 500 | state-dependent | compact weight contrast |
| Metric label | 14px / normal | same | 400/500 value | mixed | number strong, descriptor weak |
| Tab | 16px / 16px | 15px / 15px | 400 | strong/weak | selected state uses color + 2px rule |
| Code command | 16px / 24px | remains 16px / 24px | 400, highlight 500 | text/strong | ellipsis on narrow view |
| Dropdown item | 13px / 19.5px | same | 400 | `text` | intentionally denser overlay |
| Caption/index | 13–14px | 14px download labels | 400/500 | weak/weaker | bracketed or numbered notation |

**[OBSERVED]** Computed styles were measured in Chrome at the target viewports. The homepage reduces base type below 960px; the download page keeps 16px body text and only reduces selected narrow labels to 14px. **[OBSERVED]**

## Usage rules

- Keep letter-spacing `normal`; do not simulate technical character with wide tracking or uppercase. **[OBSERVED]**
- Use 400 for body, 500 for control/value emphasis, and 700 for headings. Avoid gratuitous semibold tiers. **[OBSERVED]**
- Keep headings sentence case. Reserve monospace symbols such as brackets, indices, and commands for real structure. **[INFERRED]**
- Limit paragraph width through the layout, not by shrinking type. The hero paragraph uses about 82% of the desktop inner measure and becomes 100% by 800px. **[SOURCE-VERIFIED]**

