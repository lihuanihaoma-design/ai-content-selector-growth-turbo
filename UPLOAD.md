# Upload Checklist

This repository is designed for public sharing. Before pushing or attaching files elsewhere, check the following:

1. Do not upload real exported article spreadsheets.
2. Do not upload generated reward submission workbooks.
3. Do not upload private creator priority lists.
4. Do not upload local absolute paths, credentials, cookies, tokens, or `.env` files.
5. Run the selector locally and share only sanitized summaries when needed.

Recommended release flow:

```bash
python3 -m py_compile scripts/select_biweekly_highlights.py
python3 scripts/select_biweekly_highlights.py --help
```

For a sample run, place private input spreadsheets outside the repository or under an ignored directory such as `input/`, then write outputs to `outputs/`.
