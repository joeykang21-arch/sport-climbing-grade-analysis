# Sport grade history

How each new top sport climbing grade got established, from *The Face* (8a+,
1983) to *Silence* (9c, 2017), and when 9c+ is likely to follow. The data is
scraped from [climbing-history.org](https://climbing-history.org).

**Video summary of the findings: <https://youtu.be/IUaS_ssw0tM>**

Sister project to
[bouldering-grade-history](https://github.com/joeykang21-arch/bouldering-grade-history).

## Two ways to count "first at grade"

A route's grade can change after its first ascent, so every table and model is
produced both ways:

- **`as_proposed`**: the grade the first ascentionist gave it.
- **`as_consensus`**: the grade it holds today, after repeats.

## Findings

### Four of the ten milestones change hands

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

### 9c+ looks overdue

Each method was tested by predicting 9a, 9a+, 9b, 9b+ and 9c using only the
grades before them. These are the five with the smallest typical miss (RMSE):

| Method | 9c+ estimate | Typical miss |
| --- | --- | --- |
| **Average of the last 3 gaps** | **2024.9** | **4.9 y** |
| Blend of the three gap-based methods | 2024.3 | 5.1 y |
| Polynomial (degree 2) | 2028.5 | 5.2 y |
| Widening-gap trend | 2025.5 | 5.3 y |
| Repeat the last gap | 2022.6 | 5.7 y |

All five land between **2022.6 and 2028.5**, so 9c+ is a few years overdue and
could arrive before 2030. Potential reasons for this are outlined in the video.
 The current gap (9 years since Silence) becomes the
longest on record in mid-2030 (`as_consensus`).

### Female 9c: the early-to-mid 2030s

Notebook 05 runs the same test on the female ladder, 8a (Luisa Iovane, 1986) to
9b+ (Brooke Raboutou, 2025):

| Method | Female 9c estimate | Typical miss |
| --- | --- | --- |
| **Average of the last 3 gaps** | **2032.7** | **5.3 y** |
| Polynomial (degree 2) | 2034.7 | 5.6 y |
| Polynomial (degree 1) | 2026.3 | 6.0 y |

A separate check, how far the female ladder trails the male one, gives
2028–2032. The site records no gender, so this ladder is curated in
`sportgradehistory.female_milestones` and checked against the scrape.

## Getting started

```bash
pip install -e ".[dev]"
jupyter lab notebooks/
```

`data/processed/` is committed, so the notebooks run without scraping. To
rebuild it, or re-scrape the site (rate-limited, about 3 hours, resumable):

```bash
python -m sportgradehistory.build_datasets        # cleaned datasets
python -m sportgradehistory.milestones            # disputed_ascents.csv
python -m sportgradehistory.build_visualizations  # HTML pages

python -m sportgradehistory.scrape_index          # re-scrape: listing
python -m sportgradehistory.scrape_details        # re-scrape: climb pages
```

| Notebook | What it does |
| --- | --- |
| `01_dataset_overview` | What the scrape contains; checks each data fix |
| `01b_snapshot_diff` | Compares this scrape with an older archived one |
| `02_grade_progression` | Milestones, model tests, the 9c+ estimate |
| `03_era_and_pyramids` | Routes per era, and each milestone climber's prior ascents |
| `04_timeline_figures` | Renders the timeline PNGs |
| `05_female_progression` | The female ladder and the female 9c estimate |

`visualizations/index.html` links static HTML pages for each grade era and for
the routes later upgraded or downgraded.

## The data

Scraped 2026-09-09: 7,669 climb pages. The main files in `data/processed/`
(each also saved as `.xlsx`):

| File | Rows | Contents |
| --- | --- | --- |
| `sport_routes.csv` | 2,027 | Sport routes, multi-pitch flagged |
| `sport_8a_and_above.csv` | 1,862 | The subset the timelines use |
| `regraded_routes.csv` | 87 | Routes whose grade moved off the first ascentionist's |
| `disputed_ascents.csv` | 274 | Every 9a+ and harder route with a status |
| `boulders.csv` | 3,098 | Boulder problems, for comparison |
| `milestones_*.csv` | 10 each | Milestone tables, one per convention |
| `female_milestones.csv` | 10 | Female ladder (curated) |

## Caveats

- **Only ten milestones**, so every estimate has a wide margin.
- **Year-only dates count as 1 January**, so same-year orderings can be wrong.
  They are flagged in `ordering_unresolved_with`, not guessed.
- **Disputed claims are excluded.** Akira (1995, claimed 9b) and Chilam Balam
  (2003, claimed 9b+) appear only in `timeline_with_disputed.png`.
- **Suggested grades are sparse** (254 of 1,978 sport routes), so
  `regraded_routes.csv` undercounts regrades.
- **Older records are thinner**: the site only holds what people entered.

## Source and license

Data from [climbing-history.org](https://climbing-history.org), a community
record, scraped within its `robots.txt`. Milestones were cross-checked against
Wikipedia's [grade milestones](https://en.wikipedia.org/wiki/List_of_grade_milestones_in_rock_climbing)
list. The site's terms govern the data; the code is [MIT](LICENSE).
