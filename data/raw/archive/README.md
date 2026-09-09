# Previous snapshot — diff baseline only

These two files are the **boulder repo's** raw scrape, copied from
[bouldering-grade-history](https://github.com/joeykang21-arch/bouldering-grade-history)
at `data/raw/`:

| File | Rows | Columns |
| --- | --- | --- |
| `climbs_detail.csv` | 6,844 | 10 |
| `climbs_index.csv` | 7,291 | 8 |

They exist so this repo's fresh scrape can be diffed against the state of
climbing-history.org at the time of the earlier one — which climbs are new,
which grades moved, which rows disappeared.

**They are never an input to the pipeline.** Nothing in
`src/sportgradehistory/` reads this directory; `config.ARCHIVE_*_CSV` is
defined for ad-hoc comparison and for the notebooks, and that is all. The site
is community-maintained and actively edited, so the analysis is built on the
current snapshot in `data/raw/`, not on this one.

Two differences to expect when diffing:

- `climbs_detail.csv` here has **10 columns**; the fresh scrape has **11**. The
  new one is `first_style`, which records whether the first ascent was a
  redpoint, a flash or an onsight.
- This file was collected by the older scraper and **contains the navigation-text
  and fused-location defects** described in `clean.py`. The current scraper heads
  both off at the source. Run it through `clean.clean_detail_frame` before
  comparing anything but row counts.
