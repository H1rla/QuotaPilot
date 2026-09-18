# Responsive behavior

The observations below were rendered, not inferred from desktop alone.

## Desktop — 1440 × 900

- 1080px centered shell at x=180; 1px shell boundary. Rendered section width: 1078px. **[OBSERVED]**
- 80px header and horizontal inset; inner content width 918px. **[OBSERVED]**
- Hero padding 96×80px; H1 38/57px; body 16/24px. **[OBSERVED]**
- Full navigation plus primary action. Metric illustrations are three columns with 64px gaps. **[OBSERVED]**
- Footer is five equal cells in one row; legal links stay one line. **[OBSERVED]**
- Homepage document width equals viewport; no horizontal overflow. **[OBSERVED]**

## Tablet — 768 × 1024

- Shell border disappears and content uses 24px gutters, producing a 720px inner measure. **[OBSERVED]**
- Header remains 80px and still displays desktop navigation, but hides its primary action; nav gap is 24px. **[OBSERVED]**
- Hero padding is 72×24px. H1 is 22/33px; homepage body is 15/22.5px. **[OBSERVED]**
- Install tabs remain horizontal with 32px gaps and `overflow-x:auto`; the panel stays 74px high. **[OBSERVED]**
- Media remains full-width 16:9. Standard section padding becomes 48×24px. **[OBSERVED]**
- Metric illustrations remain visible in three columns with 48px gaps. Footer remains one row. **[OBSERVED]**
- Download hero and all indexed groups already stack because 768px is below the 800px grid breakpoint. **[OBSERVED]**

## Mobile — 390 × 844

- Use 24px gutters, yielding about 342px usable inner width. Standard section padding is 48×24px. **[OBSERVED]**
- Desktop nav is replaced by a 40px menu target. The opened menu is fixed from y=80 to the viewport bottom and list rows are full width. **[OBSERVED]**
- Hero uses 48×24px padding; H1 remains 22/33px and wraps naturally. The announcement collapses to badge + short mobile link. **[OBSERVED]**
- Tabs stay in one horizontal row with scrolling. Command content truncates; the 16px copy icon remains visible. **[OBSERVED]**
- Video remains 16:9. Feature rows wrap text while syntax marker and label maintain hierarchy. **[OBSERVED]**
- Metric visual group is hidden; only the evidence statement remains. FAQ questions can wrap to two 30px lines. **[OBSERVED]**
- Newsletter control grows to 124.5px with the action inset as a full-width lower row. **[OBSERVED]**
- At 390px, footer cells stack into five 86.5px rows; legal links wrap into two lines. **[OBSERVED]**
- The observed homepage reported approximately 391px internal document width at a 390px viewport, a subpixel overflow likely caused by font/layout rounding. New implementations should clamp with `max-width:100%` and avoid preserving this artifact. **[OBSERVED, INFERRED]**
- Download rows remain single horizontal action rows; labels and row copy reduce selectively to 14px rather than shrinking the entire page. **[OBSERVED]**

## Reflow priorities

1. Remove shell borders and reduce gutters.
2. Hide the header CTA, then replace nav with a mobile panel.
3. Stack content grids at 800px.
4. Preserve install controls as scrollable one-line tools.
5. Hide decorative/statistical illustrations at 640px.
6. Move inset form actions to a second row at 480px.
7. Stack footer cells only at 400px.

**[SOURCE-VERIFIED]** Breakpoint order matches the public source; sizes above were verified in Chrome.

