# HANDOFF — scrape and cleaning session, 2026-09-09

Written for a session that has not seen the one that produced it. Everything
below is verifiable against the committed files.

## The scrape

Both scrapers ran on **2026-09-09** (UTC times in
`data/raw/scrape_manifest.json`), single-threaded, 1s per listing page and
0.5s per climb page, zero fetch errors, no unrecovered pages or ids.

| | value |
| --- | --- |
| Listing (`data/raw/climbs_index.csv`) | **8,114 rows**, 409 pages, 9 min |
| Climb pages (`data/raw/climbs_detail.csv`) | **7,669 rows**, ids 1–8511, 1h 52m |
| Climb pages skipped (0 recorded ascents) | 486 |
| Missing ids (404) | 356 |
| Previous snapshot (in `data/raw/archive/`, ~Apr 2025) | 6,844 detail / 7,291 index |

`data/raw/` is committed untouched and is the reproducibility anchor; the
archive copies are the boulder repo's raw scrape, kept **for diffing only**
(see `data/raw/archive/README.md`). The detail schema gained one column over
the archive: `first_style`.

## The three known defects, verified against this snapshot

| Defect | Status here | Fix |
| --- | --- | --- |
| 1. Nav text on the last populated column | **Absent** (0 rows) | Fixed at source: the scraper now removes the whole `div.dropdown` from the `<h1>`, surviving the site's new *Notes Log* tab. `strip_nav_suffix` in `clean.py` is dead code for this snapshot but live for the archive, and its regex was widened to the new tab spellings. |
| 2. Location fused into `climb_type` | **Absent** (0 rows) | Fixed at source: the scraper routes the heading through `split_type_and_location` at parse time. Repair kept for the archive. |
| 3. Column shift on ungraded routes | **Present, 9 rows** | 8 alpine routes (Everest, Annapurna II, Siula Grande, Nanga Parbat ×2, Gasherbrum III, Cerro Torre) repaired by `clean_detail_frame`: grade/type nulled, location rejoined. Plus one new variant, next row. |

**Climb 5873, "Substance of Everything" (8B boulder, The Frontline):** the
site's heading has no `at`/`in`/`on`, so the location fuses into the type with
nothing to split on. The defect-3 repair cannot distinguish this from a column
shift and moves everything into `location`, nulling `grade` and `climb_type`.
Net effect: **one 8B boulder is absent from `boulders.csv`**. Known, pinned by
`test_clean_detail_frame_preposition_free_fused_location_is_the_known_cost`,
left alone because it is one row and the repair's conservatism is the point.

## Processed files (CSV canonical, `.xlsx` alongside)

Rebuild everything with `python -m sportgradehistory.build_datasets`.

| File | Shape | What it is |
| --- | --- | --- |
| `climbs_detail.csv` | 7,669 × 11 | Every scraped climb, header fields repaired. Columns: `climb_id`, `climb_url`, `climb_name`, `grade` (free text, case = scale), `climb_type`, `location`, `num_ascents` (successful only, per the site), `first_climber`, `first_style` (e.g. `"Lead \| worked"`, `"Lead \| onsight"`), `first_ascent_date` (free text: `"4th Jun 2017"`, `"Jul 1998"`, `"1990"`, `"Before …"`), `first_suggested_grade` (the FA-ist's grade, **sparse** — see caveats). |
| `climbs_index.csv` | 8,114 × 8 | The cleaned listing: `climb_name`, `climb_url`, `type`, `grade`, `ascents_recorded`, `notes` (editorial free text — regrade stories often live here), `exclude_reason`, `page`. |
| `sport_routes.csv` | 2,027 × 18 | The sport dataset. Adds `grade_clean` (slash pairs → lower half, qualifiers dropped), `grade_order` (**french_ordinal** — sort on this, never the string), `is_multipitch` (bool), `yds` (approximate conversion, display only), `first_ascent` (parsed Timestamp; year/month-only anchored to period start), `first_ascent_year`, `suggested_grade_source` (null unless `first_suggested_grade` came from a cited correction in `build_datasets.SUGGESTED_GRADE_PATCHES` rather than the scrape). Sorted by grade then date. |
| `sport_8a_and_above.csv` | 1,862 × 18 | Rows of `sport_routes.csv` with `grade_order >= french_ordinal("8a")` — one notch under the first milestone (8a+, The Face, 1983). |
| `regraded_routes.csv` | 87 × 21 | Sport routes where the FA-ist's suggestion parses to a French grade different from today's consensus. Adds `suggested_clean`, `suggested_order`, `direction` (`upgrade`/`downgrade`). **Bounded by the sparse suggestion field.** |
| `boulders.csv` | 3,098 × 16 | The control group: outdoor `Boulder problem` rows, Font-ordered (`font_ordinal`), with `v_grade`. |

## The exact sport filter

```python
base_type = climb_type with "(approx) " stripped
keep = (base_type == "Sport route" or base_type == "Multi-pitch")
       and french_ordinal(grade) is not None
```

- Kept **2,027 rows**: 1,978 `Sport route` (every one French-graded — the
  scale condition is a guard, not a filter, on that type) + 49 French-graded
  `Multi-pitch` (flagged `is_multipitch=True`).
- Excluded: 253 `Multi-pitch` rows with UK trad grades (E1–E10, VS, HVS) —
  type alone cannot separate sport from trad multi-pitch; the grade scale is
  the discriminator.
- Excluded **deliberately**: 87 `Deep water solo` rows, all French-graded.
  DWS ascent history (Es Pontàs above all) is conventionally kept apart from
  the sport progression; folding it in silently would bend the milestone
  story. Revisit knowingly if wanted.
- The full distinct `climb_type` vocabulary was inspected before writing this
  (see the value_counts in the commit history); there are no `"Route"` /
  `"Trad route"` spellings in this snapshot.

## How `french_ordinal` encodes the scale

`FRENCH_SCALE` in `grades.py` is an explicit ascending list — `1, 2, 3, 4,
4a, 4b, 4c, 4+, 5, 5a, 5b, 5c, 5+, 6a … 9c` — and `french_ordinal` returns a
grade's list position (after `clean_grade` normalisation), or `None` for
anything off-scale (`E4`, `5.14d`, `Mt.`). It is **not** `font_ordinal` and is
not built on it: separate list, separate index. The scales share spellings but
not meanings (Font `8A` ≈ V11; French `8a` ≈ 5.13b), Font tops out at `9A+/9B`
while French runs to `9c`, and the sub-6 ends diverge entirely. Lookup is
case-folded as a dirty-data convenience; the caller chooses the scale by
choosing the function. The scale ends at `9c` because no harder grade has been
claimed — extend the list when the data demands it.

Dates: `parse_ascent_date` anchors year-only and month-only values to the
start of the period and treats `"Before X"` as X. So a `first_ascent` of
1990-01-01 usually means "1990, month unknown" — check `first_ascent_date`
before claiming month precision.

## Looked wrong, left alone

1. **63 detail rows (0.8%) have `num_ascents > 0` but empty first-ascent
   fields.** Cause, diagnosed against the live site: when a climb's
   chronologically **first** table entry is an unsuccessful attempt, the site
   server-renders only that leading DNF row and the remaining ascents never
   reach the HTML. `num_ascents` is still correct (it comes from the page
   text). The affected set skews toward significant routes, because those
   attract recorded pre-FA attempts: **Punks in the Gym (519)**, **Chilam
   Balam (789)**, **B.I.G (2734)**, A Muerte, The Brute, Ring of Steall, Lee
   Majors, Wende… Any milestone analysis must supplement FA climber/date for
   these from cited external sources — do not treat the empty fields as "no
   FA recorded".
2. **The site classes disputed first ascents as `dnf`.** Chilam Balam's
   4 Jul 2003 Bernabé Fernández 9b+ claim is in the ascents table with
   `class="dnf"` — the site does not count it among the 11 successful ascents.
   The scraper honours the site's judgement; the disputed-ascent analysis
   should surface these deliberately rather than rediscovering them by
   accident.
3. **Akira (475)** is carried at consensus **9a** with `first_suggested_grade`
   9b (Rouhling, 6 Jun 1995) — i.e. the site records the famous claim as a
   downgraded route, not a disputed one. It appears in `regraded_routes.csv`.
4. **`first_suggested_grade` is sparse: 254 of 1,978 sport-typed rows.**
   `regraded_routes.csv` (87 rows) can only see regrades where the site
   recorded a suggestion. The `notes` column of `climbs_index.csv` carries
   more regrade stories as free text.
   It is also occasionally *wrong* in one direction: the field can hold the
   grade a route settled at rather than the one its first ascentionist called.
   **Bibliographie (466)** is the known case — Megos proposed 9c in Aug 2020 and
   the site's own description says so, while the field records the 9b+ it landed
   on after Ghisolfi's repeat. `build_datasets.SUGGESTED_GRADE_PATCHES` corrects
   it, cited, and only while the scrape still carries the stale value.
5. **89 of 2,027 sport rows have no parseable `first_ascent`** (`NaT`), 18
   also lack `first_climber` (subset of item 1). They sort last within their
   grade rather than being dropped.
6. **Five routes carry 9c**: Silence (2017), DNA (2022), Duality of Man
   (2025), Café Colombia (2026), B.I.G (no FA fields — item 1; Schubert's FA
   was Sept 2023). Consensus on some is thin; the milestone analysis should
   treat "first at 9c" = Silence and note the rest.
7. **pandas 3.0.0 / Python 3.14** environment. Everything here runs clean on
   it; the pinned minimums in `pyproject.toml` are older.

## State of play

Done: scaffold, scrapers (4 live-site fixes, see PLAN.md §0), fresh scrape,
defect verification, cleaning, 62 tests, processed datasets. **Not yet done:**
notebooks, figures, visualizations, milestone/regression analysis, README
numbers — PLAN.md phases end here; the analysis brief takes over.
