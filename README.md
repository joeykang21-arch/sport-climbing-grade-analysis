# Sport grade history

How each new top sport climbing grade got established: scraped from
[climbing-history.org](https://climbing-history.org), cleaned, and plotted.

The sister project to
[bouldering-grade-history](https://github.com/joeykang21-arch/bouldering-grade-history),
which asks the same questions of boulder problems. This one covers sport
climbing from 1983 — Jerry Moffatt's *The Face*, the first 8a+ — to the
present, and collects the boulder rows from the same scrape so the two
progressions can be compared as a control.

**"First at grade" is ambiguous in sport climbing, and this repo does not pick
a side.** Every milestone table, timeline, figure and regression is produced
twice, under an explicit `GRADING_CONVENTION`:

- **`as_proposed`** — the grade a route was given at the time of its first
  ascent. The sport's contemporaneous belief about its own ceiling.
- **`as_consensus`** — the grade the route holds today after repeats.
  Retrospective, and it rewrites history.

Neither list is hardcoded. Both are derived from the scrape: `as_consensus`
from the current grade field, `as_proposed` from the first ascentionist's
recorded suggestion, reconstructed via `regraded_routes.csv`.

## The finding

**Four of the ten milestone grades change hands between the two conventions.**

| Grade | `as_proposed` | `as_consensus` | Moves |
| --- | --- | --- | --- |
| 8a+ | The Face, 1983 | The Face, 1983 | — |
| 8b | Les Mains Sales, 1984 | Les Mains Sales, 1984 | — |
| 8b+ | Punks in the Gym, 1985 | Punks in the Gym, 1985 | — |
| 8c | Wallstreet, 1987 | Wallstreet, 1987 | — |
| **8c+** | Hubble, 14 Jun 1990 | **Liquid Ambar, 30 Mar 1990** | 11 weeks |
| **9a** | Action Directe, 1991 | **Hubble, 1990** | 1.3 years |
| **9a+** | Biographie, 2001 | **Qui, 1996** | 5.5 years |
| **9b** | **Ali Hulk (ext. sit start), 2007** | Jumbo Love, 2008 | 0.8 years |
| 9b+ | Change, 2012 | Change, 2012 | — |
| 9c | Silence, 2017 | Silence, 2017 | — |

Under `as_consensus`, 8c+ and 9a fall **eleven weeks apart in the spring of
1990** — both dated to the day, so that ordering at least is resolved. It also
makes the 8c+ era the shortest in the sport's history, and it pulls 9a+ back
five years to 1996. Both distortions are stated wherever they bend a number;
the regression notebook does not report a fit statistic without them.

The regressions are reported **with their failure mode, not despite it**. The
global linear inverse fit puts 9c+ at 2018.5 (`as_proposed`) / 2017.4
(`as_consensus`) — already in the past — because the 1983–1991 sprint
dominates it and the sport has decelerated ever since (Spearman ρ = +0.79 /
+0.69 on interval length). Models built for a slowing sport put 9c+ between
**2022 and 2026**. Every simple reading says the next grade is overdue.

Two corrections to the popular framing, both from the data:

- **The 2017–present stall is not yet the longest in the sport's history.**
  At 9.0 years it trails Action Directe → Biographie (9.8y, `as_proposed`) and
  the 1996 9a+ → Jumbo Love (12.7y, `as_consensus`). It takes the record in
  mid-2027 or mid-2030 respectively.
- **The runway thins at the top.** 9a+ arrived over a 17-route 9a runway; 9c
  arrived with only **three** 9b+ routes standing.

## Layout

```
src/sportgradehistory/   scrapers, cleaning, milestones, dataset building
notebooks/               analysis and figure generation
data/raw/                the scrape, untouched
data/raw/archive/        the previous snapshot, for diffing only
data/processed/          cleaned and derived datasets (CSV + XLSX)
figures/                 rendered PNG timelines
visualizations/          standalone interactive HTML pages
tests/                   regression tests for the data fixes
```

## Getting started

```bash
pip install -e ".[dev]"
```

`data/processed/` is committed, so the notebooks run without scraping
anything. To rebuild it from `data/raw/`:

```bash
python -m sportgradehistory.build_datasets       # the cleaned datasets
python -m sportgradehistory.milestones           # disputed_ascents.csv + tables
python -m sportgradehistory.build_visualizations # the HTML pages
```

To re-scrape from source — single-threaded and deliberately rate-limited, so
budget two to three hours for the second command:

```bash
python -m sportgradehistory.scrape_index      # the paginated climbs listing
python -m sportgradehistory.scrape_details    # one page per climb
```

Both are resumable. They checkpoint after every page and append rows to a
`.partial.csv` as they go, so an interrupted run picks up where it stopped
rather than starting over. Re-run the same command to resume; pass
`--no-resume` to discard the checkpoint and start the range again. Progress
goes to `data/raw/scrape.log` in full and to stdout once every 100 pages;
`data/raw/scrape_manifest.json` records dates, row counts, ranges, error
counts and the commit that scraped it.

Then open the notebooks:

```bash
jupyter lab notebooks/
```

## The data

Scraped 2026-09-09: 8,114 listing rows over 409 pages, and 7,669 climb pages
carrying at least one recorded ascent, out of ids 1–8511. Zero fetch errors.

| File | Rows | What it is |
| --- | --- | --- |
| `data/raw/climbs_detail.csv` | 7,669 | One row per climb page, exactly as scraped |
| `data/raw/climbs_index.csv` | 8,114 | The listing table, with editorial notes |
| `data/processed/climbs_detail.csv` | 7,669 | The same rows with the header fields repaired |
| `data/processed/sport_routes.csv` | 2,027 | Sport routes, French-ordered, multi-pitch flagged |
| `data/processed/sport_8a_and_above.csv` | 1,862 | The hard subset the timelines are built on |
| `data/processed/regraded_routes.csv` | 86 | Routes whose consensus grade moved off the FA's suggestion |
| `data/processed/disputed_ascents.csv` | 274 | Every 9a+-and-up route with a status: consensus 108, unrepeated 132, regraded 32, **disputed 2** |
| `data/processed/boulders.csv` | 3,098 | The boulder control group, Font-ordered |
| `data/processed/milestones_*.csv` | 10 each | The milestone tables, one file per convention |

Every processed file is also written as `.xlsx`. CSV is canonical — it is what
diffs usefully in git — and the Excel copies are generated alongside it.

`data/raw/` is committed exactly as scraped. That snapshot is what keeps the
analysis reproducible once the site — community-maintained and actively
edited — moves on. `data/raw/archive/` holds the boulder repo's older scrape
(~Apr 2025) purely as a diff baseline; nothing in the pipeline reads it.

### The sport filter

`climb_type` is free text, so the filter was written against the distinct
values, not guessed:

```python
base_type in ("Sport route", "Multi-pitch")  and  french_ordinal(grade) is not None
```

Kept 2,027 rows: 1,978 `Sport route` (every one French-graded) plus 49
French-graded `Multi-pitch`, flagged `is_multipitch` rather than dropped.
Excluded: 253 multi-pitches carrying UK trad grades (E1–E10, VS, HVS) — type
alone cannot separate sport from trad multi-pitch, the grade scale can — and,
deliberately, all 87 deep water solos, whose ascent record is conventionally
kept apart from the sport progression.

### Known defects in the raw scrape, and how they are fixed

The boulder repo's scraper had three defects, each verified against this
snapshot rather than assumed:

| Defect | Status here | Fix |
| --- | --- | --- |
| **1. Navigation text** on the last populated column | **Absent** | Fixed at source: the scraper removes the whole `<h1>` dropdown, surviving the site's new *Notes Log* tab. The `clean.py` repair is dead code for this snapshot, kept for the archive. |
| **2. Location fused into the type** | **Absent** | Fixed at source: the heading goes through `split_type_and_location` at parse time. Repair kept for the archive. |
| **3. Column shift on ungraded routes** | **Present, 9 rows** | Eight alpine routes repaired by `clean_detail_frame`, plus one new preposition-free variant (climb 5873) that costs one 8B boulder — documented and pinned by test. |

The live site had also drifted in four ways since the boulder scrape, two of
which would have produced an empty dataset. They are documented in
[PLAN.md](PLAN.md) §0 and fixed in `scrape_details.py`: the ascent-count
pattern, the ascents table's new leading column, DNF rows sharing that table,
and the `<h1>` dropdown above.

### Grade handling

Grades are free text spanning five scales, which makes two things easy to get
wrong. [`grades.py`](src/sportgradehistory/grades.py) handles both:

- **Consensus-uncertain grades** are written as slash pairs (`9a/9a+`) or with
  qualifiers (`8c (soft)`). `clean_grade` reduces them to a single scale point.
- **Climbing grades do not sort lexically** (string ordering puts `7a` after
  `8c` and `10` before `3`). `french_ordinal` maps a French sport grade to its
  position on the scale, and that is what the sport datasets sort on.

`french_ordinal` and `font_ordinal` are separate functions over separate scale
lists, and neither is built on the other. The scales share spellings but not
meanings — Font `8A` ≈ V11 while French `8a` ≈ 5.13b — Font tops out at `9A+`
while French runs to `9c`, and the sub-6 ends diverge entirely. Case is how
the raw data distinguishes them, but a caller picks a scale by picking the
function, never by relying on case surviving.

## Notebooks

| Notebook | What it does |
| --- | --- |
| `01_dataset_overview.ipynb` | What the scrape contains, and a raw-vs-cleaned check of each defect |
| `01b_snapshot_diff.ipynb` | Diffs this scrape against `data/raw/archive/`: climbs added, ascents added, grades that moved |
| `02_grade_progression.ipynb` | Milestones and regressions under both conventions, the 9c+ estimate, and the 2017-to-now stall |
| `03_era_and_pyramids.ipynb` | Routes established per era, runway volume before each breakthrough, and the FA-ist's pyramid at that moment |
| `04_timeline_figures.ipynb` | Renders the poster-style PNGs into `figures/` |

## Visualizations

`visualizations/index.html` links the interactive timelines: one page per
grade era from 8a+ (1983) to the open 9c era, plus the upgrades and downgrades
recorded within each. They are plain static pages with inline CSS and inline
SVG, no JavaScript and no build step, so opening the file in a browser and
serving the directory over GitHub Pages both work.

## Caveats

- **Ten data points.** Better constrained than the boulder side's six, but
  still ten. The higher-order polynomials in notebook 02 are shown to
  demonstrate how badly they extrapolate, not as predictions. Read the linear
  fit as the honest one — and read its "9c+ was due in 2018" output as the
  model failing, not as a forecast.
- **Two milestones fall eleven weeks apart under `as_consensus`.** Liquid
  Ambar and Hubble, spring 1990. Any fit through those points is distorted,
  and notebook 02 says so wherever a fit statistic appears.
- **Some orderings are unresolved and are labelled, not guessed.** Year-only
  ascent dates anchor to 1 January, so a year-only route can appear to precede
  a dated one in the same year. Where that happens — *Les Mains Sales* vs
  *Kanal im Rücken* at 8b, *Qui* vs *Open Air* at 9a+ — the milestone tables
  carry an `ordering_unresolved_with` column rather than a verdict.
- **Disputed claims are excluded from both main timelines**, and shown in a
  third variant so the reader can see what accepting them would do. Akira
  (Fred Rouhling, 1995, claimed 9b) and Chilam Balam (Bernabé Fernández, 2003,
  claimed 9b+) would each pre-empt a milestone by 5–13 years. The source site
  backs both exclusions: it carries Akira at 9a with the 9b suggestion
  preserved, and classes Chilam Balam's 2003 first ascent as unsuccessful.
- **Punks in the Gym is carried at 8b+, and the data points away from the
  disputed 8c, not toward it.** The site's own note reads "One of the first
  8b+s in the world. Possibly slightly *easier* now than for Güllich and
  Glowacz since the construction of the birdbath hold" — an argument for a
  softer grade, not a harder one. It did not move grade between the 2025 and
  2026 snapshots, and Wikipedia's milestone list still treats it as the
  benchmark 8b+. Had consensus been 8c it would displace Wallstreet by two
  years, so the question is stated and left open rather than silently
  resolved either way.
- **63 rows have ascents recorded but no first-ascent fields**, because the
  site omits the ascent list when a climb's chronologically first entry is an
  unsuccessful attempt. Punks in the Gym, Chilam Balam and B.I.G are in that
  set; the first and third are supplemented from Wikipedia with the source
  recorded in a `supplement_source` column, and the scrape wins wherever it
  has data.
- **`first_suggested_grade` is sparse** — 254 of 1,978 sport rows — so
  `regraded_routes.csv` is a floor, not a census, and `as_proposed` assumes a
  route with no recorded suggestion was never regraded.
- **First-repeat lag is not computable from this snapshot.** Only the first
  ascent row per climb was scraped, not the full ascent list. Notebook 02 uses
  the share of each grade still unrepeated as the honest proxy and says so.
- **The record thins going back.** Pre-2000 ascent dates are often year-only,
  and the site is a retrospective community record, so early-era volumes
  reflect what was remembered and entered rather than what existed.

## Data source and etiquette

All data comes from [climbing-history.org](https://climbing-history.org), a
community-maintained record. `robots.txt` permits `/climbs` and `/climb/<id>`
and declares no crawl delay; the scrapers are single-threaded and sleep
between requests anyway (1s for the listing, 0.5s per climb page), and back
off further on error. The site's own terms govern reuse of the underlying
data; the MIT license here covers this repository's code.

Milestone claims were cross-checked against Wikipedia's
[List of first ascents (sport climbing)](https://en.wikipedia.org/wiki/List_of_first_ascents_(sport_climbing))
and [List of grade milestones in rock climbing](https://en.wikipedia.org/wiki/List_of_grade_milestones_in_rock_climbing),
both read 2026-09-09. Every disagreement is reported in notebook 02 rather
than resolved silently.

## License

[MIT](LICENSE)
