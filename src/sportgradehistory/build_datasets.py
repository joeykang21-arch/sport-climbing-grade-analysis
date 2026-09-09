"""Turn the raw scrape into the cleaned datasets the notebooks read.

Reads ``data/raw/`` and writes ``data/processed/``:

===========================  ==============================================
``climbs_detail.csv``        every scraped climb, header fields repaired
``climbs_index.csv``         the cleaned listing
``sport_routes.csv``         sport routes only, sorted by French grade then
                             date, multi-pitch rows flagged
``sport_8a_and_above.csv``   the 8a+ era subset the timelines are built on
``regraded_routes.csv``      sport routes whose consensus grade moved off the
                             first ascentionist's suggestion
``boulders.csv``             the boulder control group, Font-ordered
===========================  ==============================================

Each is written as CSV (the canonical, diff-friendly form) and as ``.xlsx``.

The sport filter, spelled out (see HANDOFF.md for the row counts it keeps):

* ``climb_type`` is ``"Sport route"`` -- every one of which carries a French
  grade in the current snapshot -- or ``"Multi-pitch"`` **with a French
  grade**, since the site types sport multi-pitches and trad multi-pitches
  identically and only the grade scale tells them apart (an ``E6`` or ``5.12``
  multi-pitch is not a sport route). An ``"(approx) "`` prefix on the type is
  accepted.
* Deep water solos are excluded: they carry French grades but their ascent
  record (Es Pontas above all) is conventionally kept apart from the sport
  progression, so folding them in silently would bend the milestone story.
* Multi-pitch rows that qualify are kept but flagged ``is_multipitch``, so the
  single-pitch progression story can drop them without losing data.

Run as::

    python -m sportgradehistory.build_datasets
"""

from __future__ import annotations

import argparse
import re

import pandas as pd

from . import config
from .clean import clean_detail_frame, clean_index_frame
from .grades import (
    add_grade_columns,
    clean_grade,
    font_ordinal,
    font_to_v,
    french_ordinal,
    french_to_yds,
    parse_ascent_date,
)

# Grades at or above this point on the French scale are the "hard" subset the
# grade-progression analysis is built on. 8a is one notch under 8a+ (The Face,
# 1983), the first milestone the analysis tracks, so the subset carries the
# context grade the era charts need without hauling the whole pyramid along.
HARD_SPORT_THRESHOLD = "8a"

SPORT_TYPES = ("Sport route",)
MULTIPITCH_TYPES = ("Multi-pitch",)
BOULDER_TYPES = ("Boulder problem", "Boulder problem (indoor)")

_APPROX = re.compile(r"^\(approx\)\s*")


def load_raw_detail(path=None) -> pd.DataFrame:
    """Load the raw climb-detail scrape."""
    return pd.read_csv(path or config.RAW_DETAIL_CSV, encoding="utf-8")


def _base_type(series: pd.Series) -> pd.Series:
    """The climb type with any ``"(approx) "`` grade marker stripped."""
    return series.astype("string").str.replace(_APPROX, "", regex=True)


def select_sport(df: pd.DataFrame) -> pd.DataFrame:
    """Return the sport routes, with grade ordering columns attached.

    The filter is the one documented at module level: sport-typed rows, plus
    multi-pitch rows whose grade is on the French scale, everything else out.
    ``is_multipitch`` records which of the two a row came from.
    """
    base = _base_type(df["climb_type"])
    is_sport = base.isin(SPORT_TYPES)
    is_multipitch = base.isin(MULTIPITCH_TYPES)
    is_french = df["grade"].map(french_ordinal).notna()

    keep = (is_sport | is_multipitch) & is_french

    sport = add_grade_columns(df[keep], ordinal=french_ordinal)
    sport["is_multipitch"] = is_multipitch[keep].astype(bool)
    sport["yds"] = sport["grade"].map(french_to_yds)
    sport["first_ascent"] = pd.to_datetime(
        sport["first_ascent_date"].map(parse_ascent_date), errors="coerce"
    )
    sport["first_ascent_year"] = sport["first_ascent"].dt.year.astype("Int64")

    # Unknown dates sort last within a grade rather than being dropped.
    return sport.sort_values(
        ["grade_order", "first_ascent"],
        ascending=[True, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def select_hard_sport(
    sport: pd.DataFrame, threshold: str = HARD_SPORT_THRESHOLD
) -> pd.DataFrame:
    """Return the sport routes graded at or above ``threshold``."""
    cutoff = french_ordinal(threshold)
    if cutoff is None:
        raise ValueError(f"{threshold!r} is not a French sport grade")
    return sport[sport["grade_order"] >= cutoff].reset_index(drop=True)


def select_regraded(sport: pd.DataFrame) -> pd.DataFrame:
    """Return sport routes whose consensus grade differs from the suggested one.

    A difference means the community moved the grade after the first ascent, so
    these rows are the upgrades and downgrades the as_proposed timeline is
    reconstructed from. ``direction`` records which way it moved. Only rows
    where the site records the first ascentionist's suggestion can appear here
    -- that field is sparse, which HANDOFF.md quantifies.
    """
    suggested_order = sport["first_suggested_grade"].map(french_ordinal)
    changed = (
        sport["first_suggested_grade"].notna()
        & suggested_order.notna()
        & sport["grade_order"].notna()
        & (suggested_order != sport["grade_order"])
    )

    regraded = sport[changed].copy()
    regraded["suggested_clean"] = regraded["first_suggested_grade"].map(clean_grade)
    regraded["suggested_order"] = suggested_order[changed]
    regraded["direction"] = (
        (regraded["grade_order"] - regraded["suggested_order"])
        .gt(0)
        .map({True: "upgrade", False: "downgrade"})
    )

    return regraded.sort_values(
        ["suggested_order", "first_ascent"],
        ascending=[True, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def select_boulders(df: pd.DataFrame, include_indoor: bool = False) -> pd.DataFrame:
    """Return the boulder problems -- the control group -- Font-ordered.

    Outdoor problems only by default, matching the boulder repo: indoor
    problems are graded on a separate consensus and would distort the
    first-ascent timelines.
    """
    types = BOULDER_TYPES if include_indoor else ("Boulder problem",)
    is_boulder = _base_type(df["climb_type"]).isin(types)

    boulders = add_grade_columns(df[is_boulder], ordinal=font_ordinal)
    boulders["v_grade"] = boulders["grade"].map(font_to_v)
    boulders["first_ascent"] = pd.to_datetime(
        boulders["first_ascent_date"].map(parse_ascent_date), errors="coerce"
    )
    boulders["first_ascent_year"] = boulders["first_ascent"].dt.year.astype("Int64")

    return boulders.sort_values(
        ["grade_order", "first_ascent"],
        ascending=[True, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def write(df: pd.DataFrame, csv_path, also_excel: bool = True) -> None:
    """Write ``df`` to ``csv_path`` and, unless disabled, to a sibling ``.xlsx``."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  {csv_path.name:<28} {len(df):>6,} rows")

    if also_excel:
        excel_path = csv_path.with_suffix(".xlsx")
        df.to_excel(excel_path, index=False)
        print(f"  {excel_path.name:<28} {len(df):>6,} rows")


def build(also_excel: bool = True) -> None:
    """Run the full raw -> processed pipeline."""
    config.ensure_dirs()

    print("cleaning climb details")
    detail = clean_detail_frame(load_raw_detail())
    write(detail, config.CLEAN_DETAIL_CSV, also_excel)

    print("building sport datasets")
    sport = select_sport(detail)
    write(sport, config.SPORT_CSV, also_excel)
    write(select_hard_sport(sport), config.SPORT_8A_PLUS_CSV, also_excel)
    write(select_regraded(sport), config.REGRADED_ROUTES_CSV, also_excel)

    print("building the boulder control group")
    write(select_boulders(detail), config.BOULDERS_CSV, also_excel)

    if config.RAW_INDEX_CSV.exists():
        print("cleaning climbs index")
        index = clean_index_frame(pd.read_csv(config.RAW_INDEX_CSV, encoding="utf-8"))
        write(index, config.CLEAN_INDEX_CSV, also_excel=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build the processed datasets from the raw scrape."
    )
    parser.add_argument(
        "--no-excel", action="store_true", help="write CSV only, skip the .xlsx copies"
    )
    args = parser.parse_args(argv)

    build(also_excel=not args.no_excel)


if __name__ == "__main__":
    main()
