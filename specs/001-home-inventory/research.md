# Phase 0 Research: Home Inventory

Everything below was verified on 2026-08-19 against current documentation or by running code
against the real `my-stuff-inventory` GCP project. Where a claim was tested, the test is shown.

---

## D1. AI extraction model — **`gemini-3.1-flash-lite` via Vertex AI, `location="global"`**

### Decision

Call Vertex AI with `google-genai` (2.18.1), model `gemini-3.1-flash-lite`, passing a Pydantic
class as `response_schema` and reading `response.parsed`.

### Evidence (run against the real project)

Listing publisher models through the SDK confirms what is actually available to us, rather than
what the docs claim:

```
gemini-3.1-flash-lite      gemini-3.5-flash-lite      gemini-2.5-flash-lite
gemini-3-flash-preview     gemini-3.6-flash           gemini-3.7-flash
```

An end-to-end extraction against a real photo returned a validated Pydantic instance:

```
latency: 2.65s
parsed: ItemSuggestion(name='Abstract 3D digital art', category='Decor', brand=None,
                       descriptor_notes='A blue abstract 3D digital image with …')
tokens in/out: 1269 53
```

### Rationale

- Both `3.1-flash-lite` and `3.5-flash-lite` work and are GA. **3.1** is chosen because it is
  cheaper ($0.25/$1.50 per Mtok vs $0.30/$2.50) and indistinguishable in quality on this task.
- `gemini-2.5-flash-lite` is cheaper still but **retires 2026-10-20**, two months out. Rejected.
- At ~1,320 tokens per extraction the cost is **$0.0004 per item** — cataloguing 1,000 items
  costs about **40 cents**, total. The model choice is not a cost lever; correctness is.
- Passing a Pydantic class gives a typed, already-validated object, so no hand-rolled JSON
  parsing and no "the model returned prose instead of JSON" failure mode.
- `Literal[...]` on the category field constrains output to our real category list, which
  removes the "model invented a category" edge case at the source rather than filtering after.

### Constraints discovered

- **Gemini 3.x is not served from `europe-north1` or `europe-west1`.** Only `global`, `us`, and
  `eu`. The Cloud Run service can still live in `europe-north1`; only the model `location` must
  be `global`. Using a regional endpoint returns a 404 that looks like a wrong model name — a
  trap worth knowing before debugging one.
- Gemini 3.x takes `thinking_level` (MINIMAL/LOW/…), **not** `thinking_budget`; the old
  parameter errors. `MINIMAL` is right for extraction.
- ADC works on Cloud Run with no key file. Needs `roles/aiplatform.user` (granted) and
  `aiplatform.googleapis.com` (enabled).

### Alternatives rejected

| Option | Why not |
|---|---|
| `gemini-3.5-flash-lite` | Works, but ~1.5× the cost for no measurable benefit here. |
| `gemini-2.5-flash-lite` | Retires in two months. |
| Gemini Developer API (API key) | An extra secret to manage and rotate; ADC on Cloud Run needs none. |

---

## D2. HEIC from iPhones — **no conversion needed for extraction**

### Decision

Send phone photos to the model as-is, whatever the browser uploads.

### Evidence (run against the real project)

```
heic bytes: 26284797
image/heic: OK -> Blue tubes pattern 3D render.
image/heif: OK -> Smooth blue tubes abstract pattern.
```

### Rationale

Vertex accepts `image/heic` and `image/heif` directly, so the "convert before we can even ask
the model" step that this design would otherwise need does not exist. Conversion is still
required for **thumbnails and browser display** (Safari renders HEIC, most other browsers do
not), but that is a display concern handled at upload time, not a blocker on the capture path.

---

## D3. Database and persistence — **SQLite in the container, snapshotted to GCS by the app**

This is the decision that changed during research, and it is the one worth reading.

### The plan we started with, and why it failed review

The intended design was Cloud Run + SQLite + **Litestream** replicating to GCS. Research found
three independent problems:

1. **It cannot scale to zero.** Litestream replicates on a background 1-second timer. Cloud
   Run's default request-based billing freezes the CPU between requests, so that timer never
   fires. Making it work requires `--no-cpu-throttling` **and** `--min-instances=1`, i.e. an
   always-on instance: **~$25–50/month** for a workload that is otherwise free. That is a 100%
   violation of the constitution's cost constraint, incurred to run a personal app used a few
   minutes a week.
2. **On GCS there is no protection against two writers.** Litestream 0.5 added lease-based
   single-writer protection, but it is implemented **only for S3**; the GCS backend has no
   leaser. Cloud Run overlaps the old and new instance on *every deploy*, so on every deploy two
   Litestream processes would write the same replica path — which Litestream's own docs say can
   leave you unable to restore.
3. **Cloud Run's filesystem is tmpfs**, so the database competes with the app for the
   instance's memory.

### The decision

Keep SQLite and keep scale-to-zero, and drop Litestream. The app manages its own persistence:

- **On startup**: download the SQLite file from `gs://my-stuff-inventory-litestream/db/inventory.sqlite`
  and remember its GCS **generation number**.
- **After each mutating request commits**: upload the file back with
  `if_generation_match=<remembered generation>`, then store the new generation.
- **If the precondition fails**: another instance wrote since we read. Refuse the write, reload
  from GCS, and return 409. This cannot silently corrupt anything.

### Evidence (run against the real project)

```
sqlite file with 2000 items: 496 KiB
upload: 1.36s  generation=1787162858946138
download: 0.44s  ok=True
fresh-generation write: ACCEPTED (expected)
stale-generation write: REJECTED (good - overlap is detectable)
```

### Rationale

- **The database is tiny — 496 KiB for 2,000 items** — because every image lives in GCS and the
  rows are just text. The entire "syncing a database file is expensive" intuition does not apply
  at this scale. Cold-start restore measured 0.44 s *from a laptop over home broadband*; from
  Cloud Run to a bucket in the same region it is faster.
- **Zero data-loss window for acknowledged writes.** The snapshot happens before the response is
  returned, so anything the owner saw save is in GCS. Litestream's async 1-second window is
  strictly worse.
- **GCS generation preconditions give us exactly the safety Litestream's GCS backend lacks** —
  tested above, a stale writer is rejected. The deploy-overlap corruption risk is closed.
- **Cost is $0**: scale-to-zero, no always-on instance, and a personal app's traffic sits inside
  the Cloud Run free tier.
- SQLAlchemy, Alembic, real SQL, joins, and FTS5 search all still apply. Nothing about the data
  model changes.
- It is roughly 50 lines of code with no new runtime dependency, versus adopting, pinning, and
  operating a separate replication daemon.

### Honest limitations

- Writes cost one full-file upload. At half a megabyte in-region this is on the order of 100 ms
  and it is only paid on save, not on browsing. If the database ever grew past a few tens of
  megabytes this design should be revisited — but at ~250 bytes per item that is tens of
  thousands of items away, well beyond the stated scale.
- Concurrent writes from two devices resolve as "second writer gets a 409 and reloads" rather
  than merging. For a single-user app this is correct behaviour, and it is what the spec's
  "last save wins, neither device shows a corrupted record" edge case asks for.
- A cold start pays the restore (~0.4 s) plus container start. Acceptable for personal use.

### Alternatives rejected

| Option | Why not |
|---|---|
| Cloud Run + Litestream + GCS | $25–50/mo, and no writer protection on GCS. See above. |
| Always-on `e2-micro` VM + Litestream | Genuinely the natural home for Litestream, and free-tier eligible — but **only in US regions**, and it means owning a VM: OS patching, disk, TLS certificates. The owner explicitly chose managed hosting over a VM. |
| Cloud Run + Firestore | Truly $0 and zero ops, but abandons SQL for a proprietary document API, and the room/category/board joins become manual denormalisation. Rejected as a bigger change than the problem warrants. |
| Cloud Run + Cloud SQL | Correct and boring, but ~$10–25/mo for a single user. |
| SQLite on a GCS FUSE mount | **Unsafe.** FUSE gives no POSIX locking and last-write-wins on whole files; SQLite's durability depends on both. This is a corruption vector, not a performance trade-off. |

---

## D4. Serving private images — **proxy through the app, not signed URLs**

### Decision

`GET /api/media/{key}` reads the object from GCS and streams it to the browser, gated by the
same session cookie as everything else.

### Rationale

- The bucket stays fully private with no public access and no URL that outlives a session
  (FR-024).
- Signed URLs would work, but from Cloud Run without a key file they require impersonation via
  the IAM `signBlob` API, an extra `roles/iam.serviceAccountTokenCreator` grant on the service
  account *on itself*, and expiry handling in the frontend. That is real complexity to save an
  in-region GCS read of a file we then have to serve anyway.
- Thumbnails are a few tens of KiB, and list and gallery views only ever request thumbnails
  (FR-023), so the bytes actually flowing through the app are small.
- Object keys are immutable, so responses are cached with `Cache-Control: private, max-age=1y`
  and the browser stops asking after the first view.

If image serving ever becomes a measurable cost or latency problem, switching to signed URLs is
a change behind one function, because the database stores **object keys, never URLs**.

---

## D5. Thumbnails — **Pillow at upload time; `pillow-heif` as a safety net**

### Decision

On upload, store the original untouched and generate one long-edge-512px WebP thumbnail. Apply
`ImageOps.exif_transpose` first. Register `pillow-heif` so HEIC decodes if it ever arrives.

### Rationale

- FR-023 requires that browsing does not download originals; a 15 MB phone photo is ~30 KB as a
  thumbnail, a 500× saving on the most frequent read path.
- Generating one thumbnail is a few hundred milliseconds of CPU on a request the owner is
  already waiting on, and it removes any need for a background job, a queue, or a second
  service.

### The HEIC situation, which is not what it first appears

Vertex accepts HEIC directly (D2), but the browser mostly makes that moot:

- **iOS Safari transcodes to JPEG** when the input is `accept="image/*"`, which is exactly what
  the capture control uses. So the common path delivers JPEG, not HEIC.
- **The trap**: adding `image/heic` to the `accept` list flips this — Safari then hands over
  HEIC, and will even transcode a JPEG *into* HEIC. So `accept` stays exactly `image/*`, and
  that is a deliberate choice rather than an incidental one.
- Pillow still has no native HEIF decoding, so `pillow-heif` is registered anyway to cover the
  share-sheet and Android paths. It ships manylinux wheels with libheif bundled, so it costs
  nothing in the Dockerfile.

### Two details that would otherwise be found the hard way

- **`ImageOps.exif_transpose` is required.** Phone photos carry rotation in EXIF; without this
  every thumbnail of a portrait photo is sideways, and only on the owner's real device.
- **Memory.** A 48 MP photo decodes to roughly 145 MB of RGB. The Cloud Run service is
  therefore sized at 1 GiB rather than the default 512 MiB, and the database shares that
  budget because the filesystem is tmpfs.

---

## D6. Local development — **`.venv` for the fast loop, Docker Compose for parity**

### Decision

Both, deliberately, each for a different job:

- **`.venv` via `uv`** for the everyday loop: `uvicorn --reload` plus `vite dev`, hot reload,
  local SQLite, images written to a local directory instead of GCS
  (`STORAGE_BACKEND=local|gcs`).
- **`docker compose up`** running the *same Dockerfile Cloud Run runs*, for pre-deploy
  verification.

### Rationale

The two catch different failures. Hot reload catches logic bugs in seconds; it will never catch
a missing system library, a frontend that was not built into the image, or a broken entrypoint —
the failures that only appear in the container. Running the production image locally means
"works on my machine" and "works on Cloud Run" are the same claim, which is the whole point of
the constitution's reproducible-environment rule.

The `STORAGE_BACKEND` switch matters more than it looks: it means UI work needs no cloud
credentials and no network, so the inner loop stays fast and offline-capable even though the
deployed app is always-online.

---

## Summary of what changed from the original brief

| Original design doc said | We are doing | Why |
|---|---|---|
| SQLite on a free-tier e2-micro VM | SQLite on Cloud Run, snapshotted to GCS | No VM to own; scale-to-zero; still $0 |
| Litestream for replication | App-managed snapshot with generation preconditions | Litestream forces an always-on instance (~$25–50/mo) and has no writer protection on GCS |
| `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | Same quality here, ~40% cheaper, both GA |
| — | `location="global"` | Gemini 3.x is not served from any `europe-*` region |
| Hardcoded password or Tailscale | Password → signed session cookie | Public URL needs a real gate; Tailscale is more setup than a password |
