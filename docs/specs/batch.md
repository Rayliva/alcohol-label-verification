# Spec — Batch review

**Status:** approved for build, Phase 3
**Date:** 2026-08-09
**Traces to:** `requirements.md` — *"during peak season, we get these big importers who dump 200, 300 label applications on us at once… If there was some way to handle batch uploads, that would be huge"* · `docs/PRD.md` P1-9, P2-12 · `docs/ui-spec.md` Screens 4–6
**Implements:** `api/app/batch/`

---

## 1. What this is

An agent uploads many label images plus one manifest pairing each image with the
values declared in its application. The service checks them, streams results as
they finish, and reports progress the whole time.

Nothing is stored. A job lives in memory for the life of the process (PRD C-2),
which is the honest shape for a prototype: an in-memory dict behind an
interface, swappable for Redis if this ever needs more than one worker.

---

## 2. Behaviour

### 2.1 The manifest — `manifest.py`

CSV or JSON. Columns are the field names the API already uses, plus `image` and
an optional `application_id`:

```
application_id,image,beverage_type,brand_name,class_type,alcohol_content,net_contents,bottler_address,country_of_origin
```

A **template** is downloadable from the API. Nobody should have to guess column
names.

**Pre-flight runs before any work starts**, and reports every mismatch
specifically, by filename or row number:

| Problem | Reported as |
|---|---|
| Manifest row names an image that was not uploaded | the row number and the filename it names |
| Uploaded image appears in no row | the filename |
| Row is missing a required field | the row number and which field |
| Header has none of the expected columns | that the file does not look like a manifest, with the expected columns listed |
| File is neither CSV nor JSON | that it could not be read as either |

A four-minute run that fails at minute three on a problem visible at second one
is the failure mode this section exists to prevent (ui-spec Screen 4).

### 2.2 The job store — `store.py`

```python
Job(id, total, done, results, errors, state, started_at, stopped)
```

`state` is `pending | running | stopped | finished`. Progress is **determinate**
— "47 of 200 checked", never a spinner (accessibility rule 8). The estimated
time remaining is computed from measured throughput, never a constant.

Results stream: a client polling mid-run sees every label finished so far, so an
agent can start on the failures before the run ends.

### 2.3 Running — `worker.py`

A bounded thread pool. Each label goes through the same `verify` the
single-label route uses — one code path, so a batch verdict and a single-label
verdict on the same image can never disagree.

An unreadable label is a result, not a failure: it lands in its own bucket and
the run continues. A label that raises anything else is recorded against its
application id with the reason, and the run continues.

`stop` is honoured between labels. Results already produced stay.

---

## 3. Boundaries

- **No persistence.** A restart loses in-flight jobs, and the README says so.
- **No queue, no retry, no scheduling.** One process, one pool.
- **No new verdict logic.** Batch calls the same pipeline.

---

## 4. Acceptance criteria

1. A manifest naming an image that was not uploaded is reported with its row
   number and the filename, before processing starts.
2. An uploaded image named in no row is reported by filename, before processing
   starts.
3. A row missing a required field is reported with its row number and the field.
4. A file whose header has none of the expected columns is rejected with the
   expected columns listed.
5. Both CSV and JSON manifests parse to the same rows.
6. A job reports `done` and `total` throughout, and `done` never exceeds `total`.
7. Results are readable while the job is still running.
8. An unreadable label is counted in its own bucket and does not stop the run.
9. Stopping a job leaves the results already produced intact.
10. The downloadable template parses cleanly through the same parser.
