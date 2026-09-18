# Composition and layout

## Marketing shell

`sticky header → optional announcement in hero → main section bands → conversion section → footer grid → legal row`

- At wide widths, center a 1080px shell with a subtle 1px left/right boundary. **[OBSERVED]**
- At ≤1040px, let the shell reach the viewport and remove its boundary. Keep section separators. **[OBSERVED]**
- Legal content lives outside the bordered shell and is centered with 32px gaps. **[OBSERVED]**

## Hero composition

`announcement → headline/supporting copy → install control → full-bleed media`

- Hero content uses 80px horizontal inset and 96px vertical inset on desktop. At ≤960px use 24px/72px; at ≤480px use 24px/48px. **[OBSERVED]**
- Keep headline and supporting copy left aligned. The desktop H1 is intentionally modest rather than billboard-sized. **[OBSERVED, INFERRED]**
- The media/demo sits directly against the shell edges beneath the hero, divided by a 1px rule, and preserves 16:9. **[OBSERVED]**

## Feature composition

`compact title + explanation → flat feature list → detached CTA`

- Standard section padding is 64px vertical / 80px horizontal desktop and 48px / 24px compact. **[OBSERVED]**
- Section heading groups use 24px bottom spacing. Within the group, H3 to copy is 12px. **[OBSERVED]**
- List content follows one vertical reading line; do not scatter features into independent cards. **[INFERRED]**

## Evidence/statistics composition

`section statement → indented three-column visual metric group`

- Give the evidence sentence equal status to other section introductions, then add visual metrics after 48px. **[OBSERVED]**
- Use line, dot, and bar texture in one quiet neutral rather than colorful charts. **[OBSERVED]**
- Remove the illustration group on mobile instead of squeezing three miniature charts. **[OBSERVED]**

## Conversion composition

`short message → single inline form`

- Keep the heading and one sentence compact. Place the form 24px after the title group. **[OBSERVED]**
- Desktop uses one long field with an inset action. Mobile reserves a clear lower action row without introducing a separate card. **[OBSERVED]**

## Download/task composition

`media/text intro card → repeated indexed two-column groups → FAQ → footer`

- Desktop intro card is `255px + 64px gap + remaining column`, 4px inner inset, 8px radius. **[OBSERVED]**
- Repeated groups are `260px label + 64px gap + content`, with 64px bottom spacing. Labels use bracketed indices and 500-weight titles. **[OBSERVED]**
- At ≤800px, stack media/text and label/content. Use 16px internal gap and 48px between groups. Media changes from square to 16:9. **[OBSERVED]**

## What belongs outside this system

The `/docs` destination was deliberately excluded. Its information architecture and application-like reading patterns must not be inferred from the marketing shell. Shared header/font use alone is not enough evidence to merge the documentation design into this Skill. **[INFERRED]**

