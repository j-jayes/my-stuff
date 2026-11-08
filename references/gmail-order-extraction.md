# Reading order history out of Gmail with Claude in Chrome

Worked out while importing clothing, Amazon and IKEA purchases into My Stuff.

## Getting at the text

- List a search with `tr.zA` rows; `[data-legacy-thread-id]` is the thread id, `td.xW span` the date.
- Do not navigate to `view=pt`: the print dialog hangs the tab. `fetch()` the same URL from the page
  instead (`/mail/u/0/?ik=${GLOBALS[9]}&view=pt&search=all&th=<id>`). It returns the whole thread,
  unclipped, and one script can loop over many threads.
- Gmail enforces Trusted Types, so `DOMParser` throws. Strip tags with regexes.
- Tool output stops at about 1000 characters in a batch. Keep the text on `window` and read it in
  950-character slices.
- The output filter blocks anything with a query string. Remove URLs from text and cut photo URLs at `?`.
- Keep batches to about three threads. A batch that times out carries on running and collides with the next.

## Per shop

| Shop | Where the items are | Notes |
| --- | --- | --- |
| Sellpy | Confirmation body | Line prices are after discount and sum to the total. Older emails say "Ditt kvitto". |
| Zalando | Body | Discounts can be order-level. Refund emails show how it was split. |
| Amazon | Body via `view=pt` | Newer titles are cut off with "...". Prices are per unit. |
| IKEA in store | PDF attachment | Open Gmail's preview by clicking "Preview attachment", then read the viewer's `innerText`. No download. |
| IKEA online | Body | Article numbers are in the email. |
| Uniqlo | Nowhere | Only returns name their items. |

Returns usually have their own email naming the item, so check for those before asking.

IKEA receipt article numbers work directly in IKEA's search API. See `home-inventory/app/ikea.py`.

## Importing

`home-inventory/scripts/import_items.py` adds items and `apply_changes.py` creates rooms and corrects
items, both through the API and both safe to re-run. Rehearse on a local server first. On this Mac
ikea.com resolves to a private address, so IKEA photos fail locally but not on Cloud Run.
