---
name: community-highlights-selector
description: Select weekly or biweekly community highlight winners from exported xlsx article spreadsheets while protecting large raw exports from model context.
---

# Community Highlights Selection Skill

Use this skill when selecting weekly or biweekly highlight winners from exported `.xlsx` article spreadsheets.

## Hard Rule

If article data has more than 100 rows, agents must not read raw rows into model context. They must process with the script first.

Allowed first step for large exports:

```bash
python3 scripts/select_biweekly_highlights.py \
  --input week1.xlsx \
  --input week2.xlsx \
  --output-prefix community_highlights_YYYY-MM-DD_YYYY-MM-DD \
  --date-label M.D-M.D \
  --workdir ./outputs
```

After the script runs, inspect only generated summaries and output tables unless the user explicitly authorizes a narrow row-level check.

## Workflow

1. Confirm input paths exist without opening large raw spreadsheets in model context.
2. Run `scripts/select_biweekly_highlights.py` with all relevant `--input` files.
3. Inspect `*_summary.md` first.
4. Inspect `*_formal.csv` and `*_reserve.csv` for review.
5. Validate that `*_reward_flow_submit.xlsx` contains exactly:

```text
UID, currency, amount, APPLICATION NUMBER
```

6. If selection needs adjustment, change CLI options or priority author inputs and rerun the script.

## Output Contract

The script must generate:

- `*_formal_list.xlsx`
- `*_reward_flow_submit.xlsx`
- `*_summary.md`
- `*_reserve.csv`
- `*_all_scored.csv`
- `*_formal.csv`

## Policy Reference

Read `references/selection_policy.md` before making manual overrides.
