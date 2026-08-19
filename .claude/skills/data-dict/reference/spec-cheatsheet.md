# data-dict.yaml — spec cheat sheet

Condensed from the [tidyverse data-dict specification](https://data-dict.tidyverse.org/)
(spec version `0.1.0`). Use this when the `data-dict` binary is not installed; when it is,
`data-dict spec` is authoritative and more current.

**All objects are closed.** An unrecognised key is a hard error, not a silently ignored one.

## Full key reference

```yaml
# --- metadata about the dictionary itself ($-prefixed) ---
$version: "0.1.0"                              # REQUIRED
$learn_more: https://data-dict.tidyverse.org/  # recommended (warning S09 if absent)

# --- describing the dataset as a whole ---
name: orders                 # terse machine-friendly id
label: Retail Orders         # short human title, plain text
description: >               # a few sentences; markdown allowed
  What this is, its grain, its population.
details: >                   # free text of any length: caveats, methodology, unknowns
  Anything else worth recording.
origin: R/clean.R            # URL or dict-relative path to the code that produced it

version:                     # version of the DATA, not the spec. Exactly one key:
  date: 2024-01-31           #   date | number (MAJOR.MINOR.PATCH) | hash

tables:
  - name: orders             # REQUIRED, non-empty, unique in the dictionary
    label: Orders
    description: >           # answer two questions: what is the grain? what is the population?
      One row per order line. Completed orders from 2020 onwards only.
    details: >
      Long-form caveats.
    origin: R/clean.R        # per-table override
    source:                  # required for validate-meta / validate-data
      parquet: orders.parquet    # relative to this yaml file; globs allowed
    constraints:             # TABLE level accepts assertions only, no barewords
      - assert: end_date >= start_date
        description: A contract cannot end before it starts.

    columns:                 # REQUIRED. Matched to data by name; order is cosmetic
      - name: order_id       # REQUIRED, non-empty, unique in the table
        label: Order ID
        description: ...     # the single most valuable field
        details: ...
        type: number(id)
        units: kg            # ONLY on number(quantity)
        time_zone: UTC       # ONLY on datetime
        display: restricted  # PII / sensitive; examples must not be real data
        constraints: [primary_key, required, unique, foreign_key]
        # then EXACTLY ONE representative-values key, chosen by type:
        examples: [1, 4821, 19004, 55210, 98311]

relationships:
  - join: orders.customer_id = customers.id   # REQUIRED. table.col = table.col, max 2 tables
    cardinality: many-to-one                  # REQUIRED. one-to-one | one-to-many | many-to-one
    description: Each order belongs to one customer.
    conflicts: [name]                         # columns on both sides with different meanings
    aliases: {mother: otters, pup: otters}    # REQUIRED for self-joins

glossary:                    # map of term -> definition, both plain strings
  BBL: >
    Borough-Block-Lot. A three-part identifier used by NYC to identify a parcel.
```

## Types

| Type | Notes |
| --- | --- |
| `string` | |
| `number(id)` | Keys and codes. **Cannot** be compared, averaged or summed |
| `number(ordinal)` | Ranks, years, sequence numbers. Can be compared, **not** averaged |
| `number(quantity)` | Weights, counts, amounts. Can be compared, averaged and summed |
| `boolean` | Carries no representative-values key |
| `date` | ISO 8601 `YYYY-MM-DD` |
| `datetime` | ISO 8601; offset-bearing unless `time_zone` is declared |
| `enum` | Always a string column; `values` are always strings |
| `struct` | Requires `fields` |
| `list(<type>)` | Nests to any depth; the representative key follows the **innermost** type |

A column may be listed with `name` only, acknowledging it without describing it. It is never
checked, but it must still exist in the data.

## Representative values — pick exactly one

| Key | For | Rules |
| --- | --- | --- |
| `examples` | `string`, `number`, `number(id)` | ~5 values. Take 5 evenly spaced along the sorted unique values, then add any surprising ones. **Quote strings that look numeric**: `["02134", "94110"]` |
| `values` | `enum` | List form `[Fruit, Grain]` when self-explanatory; map form `{A: active, D: dismantled}` when codes need decoding. **Every value must be a quoted string** if it reads as a number or boolean: `{'0': no, '1': yes}` |
| `range` | `number(ordinal)`, `number(quantity)`, `date`, `datetime` | Two-element `[min, max]`, inclusive and **observed**, not constraining. `-.inf` / `.inf` for open bounds — describe an open bound in prose |
| `fields` | `struct` | A list of reduced column descriptors |
| *(none)* | `boolean` | |

Struct `fields` support `name`, `type`, `description`, `details`, `units`, `time_zone`,
`values`, `range`, `examples`, `fields`. They do **not** support `label`, `display` or
`constraints` — put assertions about a field on the enclosing column using dot access
(`assert: LENGTH(address.zip) = 5`).

## Constraints

Column-level barewords:

- `primary_key` — the set of primary-key columns identifies each row. Implies `required` **and** `unique`.
- `foreign_key` — must have a matching `relationships` entry.
- `required` — no nulls.
- `unique` — distinct; nulls are exempt.

None of `primary_key` / `foreign_key` / `unique` is valid on a `list` or `struct`.

Assertions are maps — `{assert: <expression>, description: <optional>}` — and are the only
thing table-level `constraints` accepts.

## Expressions

Evaluated against **one row of one table**. No aggregates, no subqueries.

**A row passes when the expression is `true` OR `null`.** Only `false` is a violation, so an
assertion never doubles as a null check — pair it with `required` when non-null matters. Write
conditional rules as implications: `NOT(has_discount) OR discount_pct IS NOT NULL`.

- Operators: `+ - * /`, `= != <> < <= > >=`, `IS [NOT] NULL`, `NOT AND OR`,
  `[NOT] BETWEEN ... AND ...`, `[NOT] IN (...)`, `[NOT] LIKE` (`%`, `_`),
  `[NOT] SIMILAR TO` (RE2 regex, anchored), `CASE WHEN ... THEN ... ELSE ... END`.
- Comparisons do not chain: `lo < x < hi` is a syntax error.
- String: `LENGTH`, `LOWER`, `UPPER`, `TRIM`, `STARTS_WITH`, `ENDS_WITH`.
- Numeric: `ABS`, `FLOOR`, `CEIL`, `ROUND(x[, digits])`, `MOD(x, y)`.
- Date/time: `NOW()`, `interval(n, unit)` where unit is a bare keyword —
  `seconds`, `minutes`, `hours`, `days`, `weeks`. No `months` or `years`; use `interval(30, days)`.
- `COLUMNS(*)`, `COLUMNS('<regex>')` (unanchored), `COLUMNS([a, b, c])` — combined with `AND`,
  at most one per expression.
- No date literals: compare a temporal column against a quoted ISO string (`birthdate >= '2000-01-01'`).
- Non-identifier column names go in backticks. Because a backtick cannot start a plain YAML
  scalar, quote the whole expression when it begins with one:

  ```yaml
  - assert: '`creation date` <= NOW()'
  - assert: LENGTH(`postal code`) <= 10
  ```

## Validation

```bash
data-dict describe <file>.parquet [column]     # profile: type, distinct, missing, value sketch
data-dict validate-spec [path]                 # structure only; defaults to .
data-dict validate-meta <dict> [--table NAME]  # column names and types (reads the parquet footer)
data-dict validate-data <dict> [--table NAME]  # every value against every constraint
```

Each level implies the previous. Warnings alone still exit 0; any error exits non-zero.

## Failure codes worth memorising

| Code | Meaning |
| --- | --- |
| S01 | A `foreign_key` with no matching `relationships` entry |
| S06 | Cardinality inconsistent with the constraints — the "one" side must be `primary_key` or `unique` |
| S07 | Wrong or missing representative-values key for the type |
| S08 | `units` on something that is not `number(quantity)` |
| S12 | A value in `examples`/`range` does not match the declared type — usually an unquoted numeric-looking string |
| S13 | `range` runs backwards |
| S14 | `time_zone` on something that is not a `datetime` |
| S16 | A single-table dictionary put `description` on the table instead of the top level |
| S24 | An enum value is not a string — quote `'0'`, `'1'`, `'true'` |
| S25 | A self-join without aliases on both sides |
| S28 | Unrecognised `type` |
| M02 / M03 | Dictionary describes a column the data lacks / data has a column the dictionary ignores |
| M04 / M05 | Table declares no `source` / the source is missing or unreadable |
| D01 / D02 | Nulls in a `required` column / duplicates in a `unique` column |
| D04 / D05 | A value outside the declared enum / a foreign key with no match |
