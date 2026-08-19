---
name: data-dict
description: >-
  Write or update a data-dict.yaml documenting a dataset's tables, columns, types,
  constraints, relationships and glossary, then validate it against the real data.
  Use when starting work with a new or unfamiliar data source, or when asked to
  "document this dataset", "write a data dictionary", or "what is this column?".
---

<!-- GENERATED from .agents/skills/data-dict/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# Write a data dictionary

A data dictionary records what a dataset **means** — the part that is not recoverable from the
data itself. Types, ranges and null counts can be profiled. Grain, provenance, units, sentinel
values, which columns are trustworthy and which are quietly broken cannot.

This skill produces a `data-dict.yaml` conforming to the tidyverse
[data-dict specification](https://data-dict.tidyverse.org/), which is machine-validatable
against the actual data and diffs cleanly in git.

## Step 0 — bootstrap

Check whether the reference implementation is installed:

```bash
data-dict --help
```

**If it is**, use it and follow its own embedded guidance — it is authoritative and more current
than anything written here:

```bash
data-dict spec          # the full specification
data-dict skill-write   # the official authoring instructions
```

**If it is not**, work from `reference/spec-cheatsheet.md` next to this file, and profile with
Polars or DuckDB instead of `data-dict describe`. Offer to install it, but do not block on it:

```bash
cargo install --git https://github.com/tidyverse/data-dict data-dict-cli
```

Either way, read `reference/example-elevators.yaml` before writing your first column. It is a
real, complete dictionary and it shows the standard far better than a rule list does.

## Step 1 — profile before you write

Never infer a type from a column name. For every table, get the real shape first:

```bash
data-dict describe data/processed/orders.parquet          # per-column type, distinct, missing, value sketch
data-dict describe data/processed/orders.parquet amount   # drill into one column
```

Without the CLI:

```python
import polars as pl
df = pl.read_parquet("data/processed/orders.parquet")
print(df.schema, df.height)
print(df.null_count())
for col in df.columns:
    s = df[col]
    print(col, s.n_unique(), s.drop_nulls().head(8).to_list())
```

You are looking for: the physical type, how much is missing, how many distinct values, the
extremes, and anything that looks like a sentinel (`-9`, `999`, `""`, `1900-01-01`).

## Step 2 — interview the user. This is the step that decides quality.

**You cannot write a good data dictionary alone.** The meaning, provenance, units and gotchas
of a dataset live in the head of whoever produced it — not in the data and not in the column
names. Treat this as an interview, not a transcription job.

> A description you invented is worse than a question you asked — it looks authoritative and
> gets trusted. **When you are not certain a description is correct, you do not know it: ask.**

Never silently write a plausible-sounding description for a column whose meaning you had to
guess. Ask about:

- **What a row represents** (the grain) and **what has been filtered out** (the population).
- **Any column you would otherwise be guessing at** — cryptic names, abbreviations, codes.
  You can describe the *shape* of `flg_3`; you cannot describe what it *means*.
- **Units and sentinels.** What is `amount` measured in? Does `-9` mean "unknown"?
- **Which columns are trustworthy** versus deprecated, derived, or known-dirty.
- **Domain terms and acronyms** you do not recognise — these become glossary entries.
- **Relationships and cardinality** you cannot infer from the data alone.

Do your homework first, then ask in **batches**, and where you have a reasonable guess, offer it
as something to confirm rather than an open question:

> `amount` looks like it is in cents rather than dollars — is that right?
> `status` has values A/D/H/J/W — I can guess A is active; what are the rest?

If the user genuinely does not know, record that in `details` rather than papering over it.
"Origin unknown; inherited from the 2019 pipeline" is useful. A confident fabrication is not.

## Step 3 — write it

Place the file next to the data it describes. Under the cookiecutter-data-science layout that
is `data/processed/data-dict.yaml`, with a catalogue-level copy in `references/` if several
datasets need indexing together.

```yaml
$version: "0.1.0"
$learn_more: https://data-dict.tidyverse.org/
description: >
  What this dataset is, where it came from, and when.

tables:
  - name: orders
    source:
      parquet: orders.parquet     # relative to this yaml file
    description: >
      One row per order line. Completed orders only; cancellations are excluded.
    columns:
      - name: order_id
        type: number(id)
        constraints: [primary_key]
        description: Assigned by the ordering system; not reused after deletion.
        examples: [1, 4821, 19004, 55210, 98311]
```

The full key reference, the type vocabulary, and every validation-failure trap are in
`reference/spec-cheatsheet.md`. The ones that bite most often:

- Exactly **one** of `values` / `range` / `examples` / `fields`, chosen by type. `boolean` gets none.
- Quote anything that looks numeric but is a string: `examples: ["1", "7501T"]`, `values: {'0': no, '1': yes}`.
- `units` only on `number(quantity)`; `time_zone` only on `datetime`.
- `range` is **observed**, not aspirational — it describes what is in the data today.
- Every `foreign_key` needs a matching `relationships` entry.
- All objects are closed: a typo'd key is a hard error, not a silently ignored one.
- `display: restricted` marks PII, and its examples must not be real values.

## Step 4 — write descriptions that earn their place

Every description must say something the data does not already say. `"the user id"` for
`user_id` is worse than blank, because it takes up space and teaches nothing. If you have
nothing to add, leave it empty.

What a good description does — all of these are from the elevators example:

| Do this | Example |
| --- | --- |
| Explain *why* the type is what it is | "Stored as a string because some lots have letter suffixes (e.g. `7501T`)." |
| Quantify the damage | "Often omitted (~62% missing)." · "Over 2,000 unique values." |
| Record the cleaning | "Converted from string by fixing `O`/`o` → `0`, removing commas, and extracting leading numeric values." |
| Name the exceptions | "16 unparseable entries (e.g. `----`, `VAR`, `EX`) were set to missing." |
| Flag semantic contamination | "Some entries like `HOUSING AUTHORITY` describe ownership rather than manufacturer." |
| State how far to trust it | "Geocoded, not authoritative; some values may be in error." |
| Say which of two columns to prefer | "More reliable than street address for geolocation." |

Put domain vocabulary in the `glossary`, including phrases you used *inside* your own
descriptions. If a term would be unfamiliar to a new team member — or to the next agent — define it.

## Step 5 — validate

```bash
data-dict validate-spec data/processed/data-dict.yaml   # structure only
data-dict validate-meta data/processed/data-dict.yaml   # column names and types vs the data
data-dict validate-data data/processed/data-dict.yaml   # every value vs every constraint
```

Run all three, in that order. Each implies the previous. **When they disagree, fix the
dictionary, not the data** — the validator is telling you your description of reality is wrong.

Then confirm by inspection what the validator cannot judge: do primary keys really identify
rows uniquely, and are the descriptions still true?

A dictionary that disagrees with the data is worse than no dictionary at all, because people
will believe it.

## Maintenance

Re-run `validate-data` whenever the upstream source refreshes. That is the cheapest early
warning you will get that an external dataset changed shape underneath you.

---

This skill follows the [tidyverse data-dict specification](https://data-dict.tidyverse.org/)
and adapts its official `skill-write` guidance. The worked example is the
[NYC elevators dictionary](https://data-dict.tidyverse.org/examples/elevators.html).
