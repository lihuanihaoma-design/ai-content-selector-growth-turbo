# Community Highlights Selector

A public, dependency-free Python CLI for selecting weekly or biweekly community article highlights from exported `.xlsx` spreadsheets.

The tool reads one or more article exports, scores eligible content, enforces one award per author, and generates the files needed for editorial review and reward operations:

- `*_formal_list.xlsx`
- `*_reward_flow_submit.xlsx`
- `*_summary.md`
- `*_reserve.csv`
- `*_all_scored.csv`
- `*_formal.csv`

It is built for operators and agents who need a repeatable, auditable selection workflow without copying large private spreadsheets into chat context.

## Hard Rule For Agents

If article data has more than 100 rows, agents must not read raw rows into model context. They must process with the script first, then inspect the generated summary or output files.

This protects private creator data, reduces prompt leakage risk, and keeps selection decisions based on reproducible code instead of ad hoc spreadsheet browsing.

## What The Tool Does

The selector implements an editorial ranking workflow:

- Accepts multiple `.xlsx` exports, such as week 1 and week 2 of a biweekly cycle.
- Parses `.xlsx` files directly as zipped XML using only the Python standard library.
- Keeps only one formal award per author.
- Uses a main pool of article-type content with at least 100 characters.
- Uses long, high-quality dynamic posts only as a supplemental pool when needed.
- Prioritizes focus themes: oil, precious metals, US equities, and macro.
- Gives secondary credit to crypto market analysis, on-chain analysis, project research, DeFi, and ETF content.
- Treats creator priority lists as a light tie-breaker, not a guaranteed award.
- Treats engagement as a supporting signal, not the primary selection factor.
- Converts scientific-notation UIDs into full integer strings for reward submission.

## Requirements

- Python 3.10 or newer recommended.
- No third-party packages.
- No `pandas`.
- No `openpyxl`.
- No network access required.

## Quick Start

```bash
git clone <repo-url>
cd <repo-directory>

python3 scripts/select_biweekly_highlights.py \
  --input week1.xlsx \
  --input week2.xlsx \
  --output-prefix community_highlights_YYYY-MM-DD_YYYY-MM-DD \
  --date-label M.D-M.D \
  --workdir ./outputs
```

After the run, check `./outputs` for the formal list, reward workbook, reserve list, scoring table, and Markdown summary.

## CLI Options

```text
--input                    Required. Repeatable .xlsx input path.
--output-prefix            Required. Prefix used for every generated file.
--date-label               Optional display date range for the summary.
--workdir                  Output directory. Default: current directory.
--formal-count             Number of formal winners. Default: 30.
--reserve-count            Number of reserve candidates. Default: 10.
--target-focus-count       Target number of focus-theme formal winners. Default: 22.
--max-dynamic-formal       Maximum supplemental dynamic posts in formal winners. Default: 4.
--max-dynamic-reserve      Maximum supplemental dynamic posts in reserve. Default: 3.
--reward-amount            Reward amount written to the reward workbook. Default: 30.
--english-application      Application text for non-Chinese author names.
--chinese-application      Application text for Chinese author names.
--priority-author          Optional repeatable priority creator name.
--priority-authors-file    Optional text file with one priority creator per line.
```

## Input Spreadsheet Expectations

The script is defensive about column names. It looks for common English and Chinese headers, including:

- UID: `UID`, `uid`, `用户ID`, `user id`
- Author: `作者`, `创作者`, `昵称`, `author`, `username`
- Type: `类型`, `内容类型`, `type`, `post type`
- Title: `标题`, `文章标题`, `title`
- Content: `内容`, `正文`, `文章内容`, `content`, `body`
- Engagement: likes, comments, shares, views, and common Chinese equivalents

Rows missing an author are not selected because the one-award-per-author rule cannot be applied safely.

## Selection Policy

The detailed policy lives in the packaged skill reference directory.

At a high level:

1. Exclude short or low-quality rows.
2. Build the main pool from article-type rows with content length of at least 100.
3. Build a supplemental pool from long, high-quality dynamic rows.
4. Score by editorial relevance first, with engagement and priority creators as supporting signals.
5. Select formal winners while enforcing one award per author.
6. Fill reserve candidates from the next-best unique authors.

## Reward Workbook

The generated reward submission workbook has exactly these columns:

```text
UID, currency, amount, APPLICATION NUMBER
```

Rules:

- `currency` is always `USDT`.
- `amount` comes from `--reward-amount`.
- Chinese author names use `--chinese-application`.
- Other author names use `--english-application`.
- Scientific-notation UIDs are converted to full integer strings.

## Validation

Run these checks before publishing changes:

```bash
python3 -m py_compile scripts/select_biweekly_highlights.py
python3 scripts/select_biweekly_highlights.py --help
```

After generating outputs:

```bash
unzip -t outputs/community_highlights_YYYY-MM-DD_YYYY-MM-DD_formal_list.xlsx
unzip -t outputs/community_highlights_YYYY-MM-DD_YYYY-MM-DD_reward_flow_submit.xlsx
```

If `unzip` is unavailable on Windows, use any zip validation tool or open the workbook in Excel-compatible software.

## Agent Usage

Agents should use the packaged skill:

```text
skills/<community-highlights-skill>/SKILL.md
```

The skill instructs agents to run the CLI first for large exports, inspect `*_summary.md`, `*_formal.csv`, and `*_reserve.csv`, and avoid loading large raw exports into model context.

## Privacy Notes

This repository intentionally excludes:

- Real article exports.
- Generated reward workbooks.
- Generated winner and reserve files.
- Personal filesystem paths.
- Private creator priority lists.
- Credentials, cookies, tokens, and `.env` files.

The `.gitignore` is intentionally strict around `.xlsx`, `.csv`, and output folders. Keep private operational data outside version control.

## Why This Project Is Useful

Manual highlight selection is slow, inconsistent, and hard to audit when the input pool is large. This project turns the workflow into a reproducible process:

- Large exports are handled locally.
- Ranking criteria are explicit.
- Review artifacts are generated automatically.
- Reward submission formatting is standardized.
- Agents can operate safely without seeing raw large datasets.

The result is a practical bridge between editorial judgment and operational reliability.
