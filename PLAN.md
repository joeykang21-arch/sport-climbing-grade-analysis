# sport-grade-history — build plan

Port of [bouldering-grade-history](https://github.com/joeykang21-arch/bouldering-grade-history)
to sport climbing, 1983–present. This session: scaffold, scrape, clean. No
notebooks, no analysis.

The old repo was not on this machine (the `<PASTE PATH>` placeholder was left
unfilled), so it was cloned from GitHub into the session scratchpad and read
from there. Its package is `src/climbhistory/`; ours is `src/sportgradehistory/`.

---

## 0. Findings from verifying the old scrapers against the live site

Done before writing any code, per the brief. Four pieces of drift — two of them
would have silently produced a useless scrape.

### 0.1 robots.txt — clear to proceed

`/climbs` and `/climb/<id>` are both allowed for `User-agent: *`. The disallowed
paths are `/shuffle`, `/changes`, `/notes-log`, `/threads`, `/search` and one
climber page — none of which we touch. No `Crawl-delay` is declared, so the
brief's 1s / 0.5s is comfortably polite. Sitemap is at `/sitemap`.

### 0.2 BLOCKER — the ascent-count regex no longer matches

`scrape_details._ASCENT_COUNT` is `(\d[\d,]*)\s+successful ascents recorded`.
The page now reads:

```
Ascents  3 successful ascents  and 1 unsuccessful attempt  recorded.
```

"recorded" no longer follows "ascents", so the regex fails, `num_ascents` comes
back 0, and `scrape()` skips **every climb**. Verified: climbs 4, 6, 109, 2627,
7512 and 8200 all parse as 0 ascents under the ported code.

*Fix:* match `(\d[\d,]*)\s+successful ascents?\b` and stop requiring the
trailing word.

### 0.3 BLOCKER — the ascents table gained a leading column

Old code reads the first `<tr>` positionally as `Climber | Style | Ascent Date |
Suggested Grade`. Live headers are now:

```
['', 'Climber', 'Style', 'Ascent Date', 'Suggested Grade']
```

A blank expand-toggle column was inserted at index 0, so every field is off by
one: `first_climber` comes back empty, `first_ascent_date` gets `"Lead | worked"`,
`first_suggested_grade` gets the date.

The row structure is also richer than the old code assumes. On climb 4:

```
tr.ascent.collapsible-row          5 tds   <- an actual ascent
tr.ascent.ascent-subtitle-row      2 tds   colspan=4   "First ascent. 127 sessions."
tr.ascent.ascent-detail-row        2 tds   colspan=4   notes / references
tr.ascent.dnf.collapsible-row      5 tds   <- Adam Ondra, "Lead | did not finish"
```

Two consequences: sub-rows must be skipped, and **unsuccessful attempts sit in
the same table**, marked `class="dnf"`. Old code would report a DNF as the first
ascent on any climb whose first table row happens to be one.

*Fix:* select `tr` whose class contains `collapsible-row` and does **not**
contain `dnf`, and map cells by matching `<th>` header text to its index rather
than by hardcoded position, so the next column insertion fails loudly instead of
silently. Also capture `style` as a new column — it is what distinguishes
redpoint / flash / onsight, and it comes for free.

### 0.4 The `<h1>` nav suffix changed — defect 1 reappears unless fixed

The site added a **Notes Log** tab. Live `<h1>` for climb 4:

```html
<h1><div class="climb-title-row">
  <span>Rainman <small class="fw-normal">| 9b Sport route at
        <a href="/crag/610/malham-cove">Malham Cove</a></small></span>
  <span><div class="dropdown">
    <button class="btn btn-light dropdown-toggle"> More </button>
    <ul class="dropdown-menu">
      <li><a href="/changes?climb_id=4">Change Log</a></li>
      <li><a href="/notes-log?climb_id=4">Notes Log</a></li>   <!-- new -->
      <li><a href="/threads?climb_id=4">Threads</a></li>
    </ul></div></span>
</div></h1>
```

`_heading_text` decomposes `<a>` elements whose label is in `NAV_LABELS`.
`"notes log"` is not in that set, and `More` is a `<button>`, not a link, so
neither gets removed. The ported scraper produces:

```
location: "Malham Cove More Notes Log"        (want "Malham Cove")
```

so **defect 1 comes back in a new spelling.**

*Fix:* decompose the whole `div.dropdown` rather than matching link labels. That
removes More / Change Log / Notes Log / Threads in one go and survives the next
tab the site adds. The `NAV_LABELS` matching stays as a fallback.

### 0.5 The ID and page ranges have grown

| | old repo default | live now |
| --- | --- | --- |
| `--end-page` (listing) | 365 | page 400 still returns 20 rows; 450 returns 0 |
| `--end-id` (detail) | 7512 | 8361 exists, 8362 does not (binary search) |

Hardcoded ends would silently truncate the scrape. Both scrapers get
**auto-stop** instead: the listing stops after 3 consecutive empty pages, the
detail scraper after 150 consecutive 404s, each with an `--end-*` safety cap.

### 0.6 Encoding is fine

The server sends `charset=utf-8` and `requests` honours it — `Esclatamàsters`
round-trips correctly. Mojibake seen while probing was the Windows console, not
the data.

### 0.7 Environment

Python 3.14.0, pandas **3.0.0**, requests 2.32.5, bs4 4.14.3. pandas 3 is a
major bump from what the old repo was written against; `.astype("string")`,
`result_type="expand"` and `pd.api.types.is_scalar` all still exist, but the
ported `clean.py` gets run against the real file and the test suite before it is
trusted.

---

## Phase 1 — Scaffold  *(commit: "Scaffold repo")*

```
src/sportgradehistory/   __init__.py config.py grades.py clean.py
                         scrape_index.py scrape_details.py build_datasets.py
notebooks/               .gitkeep      (empty this session, by instruction)
data/raw/                .gitkeep
data/raw/archive/        climbs_detail.csv, climbs_index.csv   (from old repo)
data/processed/          .gitkeep
figures/                 .gitkeep
visualizations/          .gitkeep
tests/                   test_clean.py test_grades.py
LICENSE (MIT)  pyproject.toml  requirements.txt  README.md  .gitignore
.github/workflows/tests.yml
```

- `git init` in the working directory (not currently a repo).
- `pyproject.toml`: name `sport-grade-history`, package `sportgradehistory`,
  `[project.optional-dependencies] dev = [pytest, jupyter]`, console scripts
  renamed to `sportgradehistory-*`. Analysis deps (matplotlib, scikit-learn)
  stay declared so the next session does not have to touch packaging.
- `data/raw/archive/` gets the old repo's raw `climbs_detail.csv` (6,844 rows)
  and `climbs_index.csv` (7,291 rows). **Diff baseline only, never an input.** A
  `README.md` in that directory says so.

## Phase 2 — Scrapers  *(commit: "Port scrapers", then STOP)*

Ported from the old repo with the 0.2–0.5 fixes applied, plus the brief's
operational requirements, which the old scrapers had none of:

- **Single-threaded, rate-limited.** 1.0s listing, 0.5s detail; ×3 backoff on
  error. Unchanged from the old defaults.
- **Resumable.** The detail scraper appends each row to
  `climbs_detail.partial.csv` and records every *visited* id (hit, 404 or error)
  in `data/raw/.checkpoint_details.json`, flushed after every page. On restart it
  loads the checkpoint and skips visited ids. The listing scraper does the same
  per page. The final CSV is written from the accumulated partial at the end,
  sorted by id, so a resumed run produces the same file as an uninterrupted one.
- **Logging.** Verbose per-page log to `data/raw/scrape.log` (appended, so
  resumed runs keep their history). stdout gets one line per 100 pages: pages
  done, pages remaining, elapsed.
- **Manifest.** `data/raw/scrape_manifest.json` — UTC scrape start/end, wall
  time, row counts, id/page ranges, count of 404s and errors, the delays used,
  and the git commit of the scraper that produced it.
- **All climb types.** No type filter at scrape time. Boulders are the control
  group; both datasets come out of one snapshot.

New `climbs_detail.csv` column vs the old repo: `first_style` (from §0.3).
Everything else keeps the old schema, so the archive diffs column-for-column.

Runtime estimate: listing ~420 pages × 1s ≈ **8 min**. Detail ~8,400 ids ×
(0.5s sleep + ~0.4s request) ≈ **2–2.5 hours**. Budget three.

**Then I stop and hand you cmd commands to run both yourself.** I will not
launch, background or poll them. Work resumes when you say `data/raw/` is
populated.

## Phase 3 — Clean + tests  *(commit: "Clean pipeline and tests")*

1. **Verify all three known defects against the fresh raw file**, by script,
   printing counts and a few example rows — never by reading the file.
   - Defect 1 (nav text on the last populated column): expected **absent** given
     the §0.4 fix. Verify.
   - Defect 2 (location fused into type): `scrape_details` already routes through
     `split_type_and_location`, so expected absent in raw. Verify.
   - Defect 3 (column shift on ungraded routes): expected **present** — climb
     2627 still renders `"Southeast Ridge | Mt. Everest"` with no grade. Verify
     and count.
   - Record the actual incidence of each. The repairs and their tests are kept
     regardless; whichever defects score zero get labelled dead code in
     HANDOFF.md rather than deleted.
2. Port `clean.py` unchanged except: `NAV_SUFFIX` widened to match the new
   `More … Change Log … Notes Log … Threads …` shape as well as the old one, so
   the repair still works on the archive file.
3. Port `test_clean.py` and `test_grades.py`; add cases for the new nav spelling,
   for `french_ordinal`, and for the ascents-table parsing fixed in §0.3.
   `pytest -q` must pass.

## Phase 4 — Processed datasets  *(commit: "Build processed datasets")*

**Inspect before filtering, not after.** First print `climb_type.value_counts()`
in full and cross-tab it against grade-scale detection. Only then write the
filter. Expected wrinkles, to be confirmed against the data:

- **The sport filter.** `climb_type` is free text. `Sport route` is clearly in;
  `Multi-pitch` is a *separate type* that hides sport multi-pitches (climb 7512
  is `Multi-pitch` at `E4` — a trad grade), so type alone cannot decide it.
  Plan: include a row when its type is sport-ish **and** its cleaned grade sits
  on the French scale (`french_ordinal` is not None). That drops E-graded and
  YDS-graded multi-pitches without hand-listing types. The final rule and its row
  count go into HANDOFF.md.
- **Single- vs multi-pitch.** Both stay in the dataset; a boolean `is_multipitch`
  flags the multi-pitch rows so the progression story can filter to single-pitch
  without losing data.
- **`french_ordinal`.** Already exists in the old `grades.py` and is *not*
  `font_ordinal` — separate `FRENCH_SCALE` list, lowercase-keyed index. Ported
  as-is, verified against the live grade vocabulary, and extended only if the
  scrape turns up grades it does not cover. Font stays uppercase-keyed; the two
  are never merged.
- **Slash grades and qualifiers** already go through `clean_grade` (`9a/9a+` →
  `9a`, `8c (soft)` → `8c`, `(approx) 8b` → `8b`). Pinned by test.

Outputs (CSV canonical, `.xlsx` alongside, per the old repo's convention):

| File | What |
| --- | --- |
| `processed/climbs_detail.csv` | all climbs, header fields repaired |
| `processed/climbs_index.csv` | cleaned listing |
| `processed/sport_routes.csv` | the sport filter, `is_multipitch` flagged, sorted by French ordinal then date |
| `processed/sport_8a_and_above.csv` | the hard subset |
| `processed/sport_regraded.csv` | consensus grade ≠ first ascentionist's suggestion |
| `processed/boulders.csv` | the control group, Font-ordered |

## Phase 5 — HANDOFF.md  *(commit: "Add handoff notes")*

Written for a reader who has not seen this conversation: scrape date and row
counts; every processed file with its shape and column meanings; which of the
three defects actually occurred and how each was fixed; the exact sport filter
and how many rows it kept; how `french_ordinal` encodes the scale and why it is
not `font_ordinal`; and a list of things that looked wrong but were left alone.

---

## Decisions I want confirmed before I start

1. **Cloning the old repo from GitHub** instead of a local path — fine? If you
   have a local clone with uncommitted work, give me that path instead.
2. **Adding `first_style`** to the detail schema (§0.3). Nearly free, and it is
   how redpoint / flash / onsight and DNFs get told apart — which matters more
   for sport than it did for boulders. Say no and I keep the schema identical to
   the old repo.
3. **`--end-id` safety cap of 9000** on the detail scraper (highest live id is
   8361), with auto-stop after 150 consecutive 404s. Say if you want it wider.
