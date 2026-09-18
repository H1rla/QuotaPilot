# Design principles

These rules transfer the observed design language without copying the reference product.

1. **Use monospace as the interface voice.** The entire marketing page—not only code—is set in the same mono stack. Developer identity comes from rhythm, syntax-like labels, and compact weight changes rather than fake terminal chrome. **[OBSERVED, SOURCE-VERIFIED]**
2. **Build hierarchy with bands and rules.** A centered desktop shell and 1px separators organize the page. Most sections are flat and share a background; shadows are absent except for transient overlays. **[OBSERVED]**
3. **Keep the content measure disciplined.** At wide widths, use an approximately 1080px outer shell and 920px inner measure. A repeated 80px inset makes unrelated sections feel like one system. **[OBSERVED]**
4. **Let weight, tone, and whitespace do more than size.** The page uses few type sizes. Strong headings, medium labels, muted body text, and large vertical intervals create hierarchy without oversized editorial display text. **[OBSERVED, INFERRED]**
5. **Use warm near-neutrals and ration chroma.** Warm white, charcoal, and three muted gray tiers carry almost the entire page. Pale yellow-green appears for selection/focus feedback, not as a large brand wash. **[OBSERVED, SOURCE-VERIFIED]**
6. **Keep structure square; soften controls slightly.** Page bands, statistics, lists, and footer cells are square. Buttons and command actions use 4px, compound inputs/tabs use 6px, and the exceptional download media card uses 8px. **[OBSERVED]**
7. **Express technical credibility through notation.** Bracketed indices, `[*]` markers, commands, terse labels, thin charts, and copy affordances evoke tooling without turning the page into a terminal simulation. **[OBSERVED, INFERRED]**
8. **Prefer calm density over sparse spectacle.** Copy, feature rows, and metrics are information-rich, but fixed gutters, 1.8–2.0 line-height for prose, and 48–64px section padding keep them readable. **[OBSERVED]**
9. **Remove secondary spectacle before compressing primary content.** At mobile widths, the statistics illustrations disappear, prose remains, the command truncates safely, and controls reflow. **[OBSERVED, SOURCE-VERIFIED]**
10. **Keep motion brief and state-driven.** Most elements change instantly. Where transitions exist, they last roughly 150–200ms and affect background, opacity, or compact active scale only. **[OBSERVED, SOURCE-VERIFIED]**

The dominant hierarchy mechanisms are whitespace, type tone/weight, and 1px boundaries. Background contrast is secondary. Persistent shadow and ornamentation are intentionally rare. **[INFERRED]**

