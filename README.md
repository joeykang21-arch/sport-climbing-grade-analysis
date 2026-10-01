# Sport grade history

How each new top sport climbing grade got established, from *The Face* (8a+,
1983) to *Silence* (9c, 2017). The data is scraped from
[climbing-history.org](https://climbing-history.org), cleaned, and modelled to
estimate when the next grade arrives.

Sister project to
[bouldering-grade-history](https://github.com/joeykang21-arch/bouldering-grade-history).
The same scrape's boulder rows are kept here as a control group.

## Two ways to count "first at grade"

A route's grade can change after its first ascent, so "the first 9a" depends on
which grade you use. Every table, figure and model here is produced both ways:

- **`as_proposed`**: the grade the first ascentionist gave it.
- **`as_consensus`**: the grade it holds today, after repeats.

Both are derived from the scrape, not hardcoded.

## Findings

### Four of the ten milestones change hands between the two conventions

| Grade | `as_proposed` | `as_consensus` | Gap |
| --- | --- | --- | --- |
| 8a+ | The Face, 1983 | same | — |
| 8b | Kanal im Rücken, 1984 | same | — |
| 8b+ | Punks in the Gym, 1985 | same | — |
| 8c | Wallstreet, 1987 | same | — |
| **8c+** | Hubble, Jun 1990 | **Liquid Ambar, Mar 1990** | 11 weeks |
| **9a** | Action Directe, 1991 | **Hubble, 1990** | 1.3 years |
| **9a+** | Biographie, 2001 | **Qui, 1996** | 5.5 years |
| **9b** | **Ali Hulk (ext. sit start), 2007** | Jumbo Love, 2008 | 0.8 years |
| 9b+ | Change, 2012 | same | — |
| 9c | Silence, 2017 | same | — |

Under `as_consensus`, 8c+ and 9a land eleven weeks apart, which distorts any
curve fitted through them. Notebook 02 flags this wherever it matters.

### 9c+ looks overdue

- A straight-line fit puts 9c+ in **2018** (`as_proposed`) or **2017**
  (`as_consensus`), already in the past. That is the model failing: the fast
  1983–1991 run dominates it, and the gaps between grades have grown since.
- Models built for a slowing sport put 9c+ between **2022 and 2026**.
- The current gap (9 years since 2017) is not yet the longest. It passes
  Action Directe → Biographie (9.8 years, `as_proposed`) in mid-2027 and
  Qui → Jumbo Love (12.7 years, `as_consensus`) in mid-2030.
- Fewer routes exist at the top grade before each breakthrough: 9a+ arrived
  with 17 routes at 9a, while 9c arrived with only three at 9b+.

### Female ladder: female 9c in the early-to-mid 2030s

Notebook 05 applies the same tests to the female ladder: 8a (Luisa Iovane, 1986)
to 9b+ (Brooke Raboutou, 2025).

Hiding only the top rung makes a cubic curve look excellent: it lands within six
months of the real 9b+. Making every method predict five rungs it never saw
reverses that, and the cubic finishes seventh of ten. The winner is the simplest
method, which also wins on the men's ladder:

| Method | Female 9c | Typical miss |
| --- | --- | --- |
| **Average of the last 3 gaps** (selected) | **2032.7** | **5.3 y** |
| Poly 2 (best curve) | 2034.7 | 5.6 y |
| Poly 1 | 2026.3 | 6.0 y |
| Poly 3 (won the single-rung test) | 2031.2 | 10.9 y |

A separate check (how far the female ladder trails the male one, grade for
grade) gives 2028–2032. Female 9c+ is two steps past the data, so it gets no
estimate.

The site records no gender, so this ladder is curated in
`sportgradehistory.female_milestones` and checked against the scrape. All eight
routes the site carries agree on grade. Come Back and Choucas rely on the
external source alone.

### Flash ladder: 9b first try is due now

Notebook 06 runs the same tests on the hardest grade climbed **first try**: 7b+
(Edlinger, 1982) to 9a+ (Ondra, Super Crackinette, 2018). The same reversal
happens again: a quartic wins the single-rung test and finishes ninth of ten on
the five-rung test.

| Method | 9b first try | Typical miss |
| --- | --- | --- |
| **Poly 2** (selected) | **2026.1** | **3.2 y** |
| Average of the last 3 gaps | 2022.6 | 3.3 y |
| All eight methods under six years | 2019.0–2026.8 | — |
| Lag behind the redpoint ladder | 2026–2030 | — |

The top two are effectively tied. The ladder has been stuck for 8.6 years and
breaks its own record gap (9.8 years) in late 2027. Caveats: it mixes flash with
onsight, has no recorded 8a+, and its first two rungs share the year 1982.

## Getting started

```bash
pip install -e ".[dev]"
jupyter lab notebooks/
```

`data/processed/` is committed, so the notebooks run without scraping. To
rebuild from `data/raw/`:

```bash
python -m sportgradehistory.build_datasets        # cleaned datasets
python -m sportgradehistory.milestones            # disputed_ascents.csv
python -m sportgradehistory.build_visualizations  # HTML pages
```

To re-scrape (rate-limited; the second step takes 2–3 hours):

```bash
python -m sportgradehistory.scrape_index
python -m sportgradehistory.scrape_details
```

Both resume where they stopped if interrupted (`--no-resume` starts over). Logs
go to `data/raw/scrape.log`, and `data/raw/scrape_manifest.json` records what
was scraped and when.

## Layout

```
src/sportgradehistory/   scrapers, cleaning, milestones, dataset building
notebooks/               analysis and figures
data/raw/                the scrape, untouched (archive/ = older snapshot, for diffing)
data/processed/          cleaned and derived datasets (CSV + XLSX)
figures/                 rendered PNGs
visualizations/          standalone HTML pages
tests/                   regression tests for the data fixes
```

### Notebooks

| Notebook | What it does |
| --- | --- |
| `01_dataset_overview` | What the scrape contains; checks each data fix |
| `01b_snapshot_diff` | Compares this scrape with the older archived one |
| `02_grade_progression` | Milestones, model tests, the 9c+ estimate, the current gap |
| `03_era_and_pyramids` | Routes per era, and each milestone climber's prior ascents |
| `04_timeline_figures` | Renders the timeline PNGs |
| `05_female_progression` | The female ladder and the female 9c estimate |
| `06_flash_progression` | The flash ladder and the 9b-first-try estimate |

### Visualizations

Open `visualizations/index.html`. It links one page per grade era plus pages
that span all eras: `runway-by-grade.html` (what was climbed at a grade before
the next arrived), `upgrades-by-grade.html` and `downgrades-by-grade.html`
(routes later graded differently from the first ascentionist's call), and
`boulder-regrades-by-grade.html` (the same for boulders). They are static HTML
with no JavaScript, so they also work on GitHub Pages.

## The data

Scraped 2026-09-09: 7,669 climb pages with at least one ascent, zero fetch
errors. Every processed CSV also has an `.xlsx` copy; the CSV is the source of
truth.

| File | Rows | Contents |
| --- | --- | --- |
| `data/raw/climbs_detail.csv` | 7,669 | One row per climb page, as scraped |
| `data/raw/climbs_index.csv` | 8,114 | The site's listing table |
| `processed/climbs_detail.csv` | 7,669 | Same rows, header fields repaired |
| `processed/sport_routes.csv` | 2,027 | Sport routes, multi-pitch flagged |
| `processed/sport_8a_and_above.csv` | 1,862 | The subset the timelines use |
| `processed/regraded_routes.csv` | 87 | Routes whose grade moved off the first ascentionist's |
| `processed/disputed_ascents.csv` | 274 | Every 9a+ and harder route with a status (2 disputed) |
| `processed/boulders.csv` | 3,098 | Boulder control group |
| `processed/milestones_*.csv` | 10 each | Milestone tables, one per convention |
| `processed/female_milestones.csv` | 10 | Female ladder (curated) |
| `processed/flash_milestones.csv` | 10 | Flash ladder (curated) |
| `processed/*_model_scores.csv` | 10 | Each method's test record and estimates |
| `processed/milestone_sport_pyramids.csv` | 10 | Each milestone climber's prior ascents by grade |

**What counts as sport:** `Sport route` rows plus French-graded `Multi-pitch`
rows (flagged). Trad-graded multi-pitches and deep water solos are excluded.

**Grades** are parsed by [`grades.py`](src/sportgradehistory/grades.py).
`clean_grade` reduces `9a/9a+` or `8c (soft)` to one grade, and
`french_ordinal` / `font_ordinal` sort grades on their own scales. Sport and
boulder grades share spellings but not meanings (French 8a ≠ Font 8A), so the
two scales are never mixed.

**Scrape fixes:** the older boulder scraper had three known defects; two are
fixed at source and one (nine rows with shifted columns) is repaired in
cleaning. Four site changes since then are handled in `scrape_details.py`; see
[PLAN.md](PLAN.md) §0.

## Caveats

- **Only ten milestones.** High-order polynomials are shown to demonstrate how
  badly they extrapolate, not as forecasts.
- **Same-year orderings are flagged, not guessed.** A date of "1984" counts as
  1 January, so it can wrongly sort before a dated ascent that year. These
  pairs are listed in `ordering_unresolved_with`. The one hand-made call:
  Kanal im Rücken (dated 24 Oct 1984) gets 8b over Les Mains Sales ("1984"),
  matching Wikipedia (`TIE_BREAKS` in `milestones.py`).
- **Disputed claims are left out of the main timelines.** Akira (1995, claimed
  9b) and Chilam Balam (2003, claimed 9b+) appear only in
  `timeline_with_disputed.png`. The site itself grades Akira 9a and records
  Chilam Balam's first ascent as unsuccessful.
- **Punks in the Gym stays at 8b+.** Some call it 8c, but the site's note
  suggests it has got easier. At 8c it would take that milestone from
  Wallstreet; the question is left open.
- **63 climbs lack first-ascent details** because the site hides them when the
  first entry is a failed attempt. Punks in the Gym and B.I.G are filled in
  from Wikipedia (marked in `supplement_source`).
- **Suggested grades are sparse** (254 of 1,978 sport rows), so
  `regraded_routes.csv` undercounts. Where the field is clearly wrong it is
  patched with a citation in `build_datasets.SUGGESTED_GRADE_PATCHES`
  (e.g. Bibliographie, proposed 9c).
- **No repeat dates.** Only each climb's first ascent was scraped, so notebook
  02 uses the share of routes still unrepeated instead.
- **The female ladder is partly external.** Two rungs are missing from the
  scrape, three dates are year-only, and its 14.5-year 9a → 9a+ gap reflects
  participation as much as difficulty.
- **Older records are thinner.** Pre-2000 dates are often year-only, and the
  site only holds what people remembered to enter.

## Source and license

Data from [climbing-history.org](https://climbing-history.org), a community
record. `robots.txt` allows the scraped pages; the scrapers are single-threaded
and pause between requests. Milestones were cross-checked against Wikipedia's
[sport first ascents](https://en.wikipedia.org/wiki/List_of_first_ascents_(sport_climbing))
and [grade milestones](https://en.wikipedia.org/wiki/List_of_grade_milestones_in_rock_climbing)
lists (read 2026-09-09); notebook 02 reports every disagreement.

The site's terms govern the data; the code is [MIT](LICENSE).
