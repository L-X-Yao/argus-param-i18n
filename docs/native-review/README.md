# Native-speaker review kit (2026-11-22)

This kit is for a **human native speaker** of one of the nine translation locales. It is not a
machine review; the machine cross-model review is in
[`../TRANSLATION_REVIEW_2026-11-22.md`](../TRANSLATION_REVIEW_2026-11-22.md).

## Files

| File | Rows | What it is |
|---|---:|---|
| `2026-11-22-params.csv` | 270 | 30 high-risk parameter strings × 9 locales (arming, failsafe, battery, navigation, calibration, logs, fence) |
| `2026-11-22-ui.csv` | 456 | 57 firmware/log/preflight UI strings × 8 non-Chinese locales |

Columns are `locale,param/key,field,english,current_translation` (`hash` is present on parameter
rows for traceability).

## How to review

1. Filter one locale. Read the English and the current translation side by side.
2. Add three columns: `verdict` (`ok` / `needs_fix`), `suggested`, `notes`.
3. Judge meaning first: safety actions, directions (higher/lower, before/after), negation, and
   units. Then terminology and fluency.
4. Keep parameter names, numbers, units and placeholders (`{board}`, `{size}`, `{n}`) unchanged.
5. Do not edit `tm/` or the Argus locale files from this kit. Return the filled CSV; the
   maintainer will turn accepted fixes into a new data version.

The samples are targeted, not exhaustive. A clean result does not mean the whole locale is
reviewed; record the reviewer name, locale, date and the number of rows checked.

## Current state

- Data: `data-v2026.11.6`; all nine locales are machine-translated (`reviewed: 0`).
- The 2026-11-22 machine review found 0 high / 4 medium / 13 low issues; those are fixed in
  `data-v2026.11.5`.
- Native review is the remaining quality step before claiming a locale is reviewed.
