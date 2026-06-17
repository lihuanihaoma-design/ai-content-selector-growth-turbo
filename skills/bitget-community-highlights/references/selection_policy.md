# Selection Policy

This policy defines how to select weekly or biweekly community highlight winners from exported article spreadsheets.

## Non-Negotiable Safety Rule

If article data has more than 100 rows, agents must not read raw rows into model context. They must process with the script first.

Use generated outputs for inspection:

- `*_summary.md`
- `*_formal.csv`
- `*_reserve.csv`
- `*_all_scored.csv`

## Eligibility

Main pool:

- Content type is article-like.
- Content length is at least 100 characters.
- Row is not low quality.

Supplemental pool:

- Content type is dynamic-like.
- Content is long enough to show real analysis.
- Content matches at least one priority or secondary theme.
- Used only when the main pool cannot fill the target cleanly.

Excluded:

- Missing author.
- Very short content.
- Obvious test, spam, repost, giveaway, or engagement-bait rows.
- Unsupported content types.

## Award Rules

- One award per author.
- Formal winners are selected before reserve candidates.
- Reserve candidates also respect one author per selected row.
- Supplemental dynamic posts are capped separately for formal and reserve outputs.

## Theme Priority

Focus themes:

- Oil.
- Precious metals.
- US equities.
- Macro.

Secondary themes:

- Crypto market analysis.
- On-chain analysis.
- Project research.
- DeFi.
- ETF.

Focus themes should drive the formal list when enough qualified rows exist. Secondary themes provide breadth and should help strong analysis surface without replacing the focus-theme target.

## Priority Creators

Priority creators are a light tie-breaker only.

They should never guarantee selection, override quality filters, or bypass the one-award-per-author rule.

## Engagement

Engagement is a supporting signal. It can help distinguish similar articles, but it should not outweigh topic relevance, content quality, or operational constraints.

## Manual Override Standard

Manual overrides should be rare. If used, document:

- Which row changed.
- Why the automatic ranking was insufficient.
- Whether the override affects reward submission.
- Whether the selection still respects one award per author.
