# Sport grade history

How each new top sport climbing grade got established: scraped from
[climbing-history.org](https://climbing-history.org), cleaned, and plotted.

The sister project to
[bouldering-grade-history](https://github.com/joeykang21-arch/bouldering-grade-history),
which asks the same questions of boulder problems. This one covers sport
climbing from 1983 — Wolfgang Güllich's *Kanal im Rücken*, the first 8b — to the
present, and it collects the boulder rows from the same scrape so the two
progressions can be compared as a control.

## Layout

```
src/sportgradehistory/   scrapers, cleaning, dataset building
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

`data/processed/` is committed, so the notebooks run without scraping anything.
To rebuild it from `data/raw/`:

```bash
python -m sportgradehistory.build_datasets
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
`--no-resume` to discard the checkpoint and start the range again.

Progress goes to `data/raw/scrape.log` in full, and to stdout once every 100
pages. `data/raw/scrape_manifest.json` records what each run produced: dates,
row counts, id and page ranges, error counts, and the commit that scraped it.

## The data

`data/raw/` is committed exactly as scraped. That snapshot is what keeps the
analysis reproducible once the site — which is community-maintained and
actively edited — moves on.

Row counts, column meanings, the defects found in this snapshot and the exact
sport filter used are all in [HANDOFF.md](HANDOFF.md).

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
meanings — Font `8A` is nowhere near French `8a` — so a grade is only ever
looked up in the scale its caller asked for.

## Data source and etiquette

All data comes from [climbing-history.org](https://climbing-history.org), a
community-maintained record. `robots.txt` permits `/climbs` and `/climb/<id>`
and declares no crawl delay; the scrapers are single-threaded and sleep between
requests anyway (1s for the listing, 0.5s per climb page), and back off further
on error. The site's own terms govern reuse of the underlying data; the MIT
license here covers this repository's code.

## License

[MIT](LICENSE)
