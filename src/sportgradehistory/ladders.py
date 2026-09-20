"""Shared machinery for curated milestone ladders.

Some ladders in this repository cannot be derived from the scrape. The female
ladder is one (the scrape has no gender field, and its milestones are repeats,
which this snapshot did not keep); the hardest-flash/onsight ladder is another
(a flash is an ascent *style*, and the scrape kept only each climb's first
ascent row). Both are therefore curated tables with external sources, and both
need the same three things done to them:

* turned into a frame with grade ordinals, step indices and parsed dates;
* checked against the scrape wherever the scrape carries the route;
* audited for orderings the dates cannot settle.

This module holds that logic once. The ladders themselves live in
:mod:`sportgradehistory.female_milestones` and
:mod:`sportgradehistory.flash_milestones`, which own their tables, their
sources and their caveats, and delegate the mechanics here.

**A ladder may have holes.** ``steps`` is the position on the French scale
relative to the ladder's start grade, not a row counter, so a grade with no
recorded ascent is simply absent and the steps either side of it differ by
more than one. Every consumer must read ``steps`` rather than assume the rows
are consecutive — the flash ladder has no recorded 8a+, and treating its rows
as evenly spaced would compress a two-grade jump into one.
"""

from __future__ import annotations

import pandas as pd

from . import config
from .grades import french_ordinal, parse_ascent_date
from .milestones import date_precision


def build_ladder(entries: list[dict], start_grade: str) -> pd.DataFrame:
    """Turn a curated milestone list into an ordered frame.

    Adds ``grade_order`` (French ordinal), ``steps`` (rungs above
    ``start_grade``, with gaps preserved), ``ascent`` (parsed Timestamp, coarse
    dates anchored to the start of their period exactly as
    :func:`~sportgradehistory.grades.parse_ascent_date` does everywhere else),
    ``date_precision`` and ``year_frac``.

    Ordered by grade, not by date: for these ladders the two are not always the
    same sequence. See :func:`ordering_notes`.
    """
    base = french_ordinal(start_grade)
    if base is None:
        raise ValueError(f"start grade is off the French scale: {start_grade!r}")

    rows = []
    for entry in entries:
        order = french_ordinal(str(entry["grade"]))
        if order is None:
            raise ValueError(f"unparseable grade: {entry['grade']!r}")
        ascent = parse_ascent_date(entry["date_raw"])
        if ascent is None:
            raise ValueError(f"unparseable date: {entry['date_raw']!r}")
        rows.append({
            **entry,
            "grade_order": order,
            "steps": order - base,
            "ascent": ascent,
            "date_precision": date_precision(entry["date_raw"]),
            "year_frac": ascent.year + (ascent.dayofyear - 1) / 365.25,
        })
    return pd.DataFrame(rows).sort_values("grade_order").reset_index(drop=True)


def ordering_notes(ladder: pd.DataFrame) -> pd.DataFrame:
    """Consecutive rungs whose dates do not order the way the grades do.

    Two cases are reported, and neither is silently fixed:

    * an **inversion**, where the harder grade carries the earlier date;
    * a **tie**, where two rungs land on the same anchored date.

    Both are usually artifacts of anchoring — a year-only date resolves to
    1 January, so it sorts ahead of every dated rival in its year, and two
    year-only rungs in the same year become indistinguishable. Where the pair
    is fully dated, the ordering is real and ``anchoring_artifact`` is False.
    """
    rows = []
    for (_, lower), (_, upper) in zip(ladder.iloc[:-1].iterrows(),
                                      ladder.iloc[1:].iterrows()):
        if upper["year_frac"] > lower["year_frac"]:
            continue
        coarse = [r for r in (lower, upper) if r["date_precision"] != "day"]
        rows.append({
            "lower_grade": lower["grade"],
            "lower_route": lower["route"],
            "lower_date": lower["date_raw"],
            "upper_grade": upper["grade"],
            "upper_route": upper["route"],
            "upper_date": upper["date_raw"],
            "kind": "tie" if upper["year_frac"] == lower["year_frac"] else "inversion",
            "inversion_years": round(lower["year_frac"] - upper["year_frac"], 2),
            "anchoring_artifact": bool(coarse),
        })
    return pd.DataFrame(rows)


def missing_rungs(ladder: pd.DataFrame, start_grade: str) -> list[str]:
    """Grades between the ladder's ends that carry no recorded ascent.

    A hole is a real property of the record, not a bug, so it is reported
    rather than interpolated over. The fits read ``steps``, so an absent rung
    costs a data point without distorting the spacing of the others.
    """
    from .grades import FRENCH_SCALE

    base = french_ordinal(start_grade)
    present = set(ladder["grade_order"])
    return [FRENCH_SCALE[o] for o in range(base, int(ladder["grade_order"].max()) + 1)
            if o not in present]


def crosscheck(entries: list[dict], sport: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compare every row of a curated ladder against the scrape, where it can.

    Returns one row per milestone with the site's consensus grade and first
    ascent beside the curated values, plus ``grade_agrees``. A ``False`` there
    means the curated table and the scrape disagree about what grade the route
    is, which invalidates the row — not a rounding difference.

    ``is_own_fa`` marks the rows where the milestone climber is also the
    route's first ascentionist, which each ladder interprets for itself.
    """
    if sport is None:
        sport = pd.read_csv(config.SPORT_CSV)

    indexed = sport.set_index("climb_id")
    rows = []
    for entry in entries:
        climb_id = entry.get("climb_id")
        row = {
            "grade": entry["grade"],
            "route": entry["route"],
            "climber": entry["climber"],
            "ascent_date": entry["date_raw"],
            "climb_id": climb_id,
        }
        if climb_id is None or climb_id not in indexed.index:
            rows.append({**row, "site_name": None, "site_grade": None,
                         "grade_agrees": None, "site_fa_climber": None,
                         "site_fa_date": None, "is_own_fa": None})
            continue
        site = indexed.loc[climb_id]
        own_fa = (str(site["first_climber"]).strip().casefold()
                  == str(entry["climber"]).strip().casefold())
        rows.append({
            **row,
            "site_name": site["climb_name"],
            "site_grade": site["grade_clean"],
            "grade_agrees": site["grade_clean"] == entry["grade"],
            "site_fa_climber": site["first_climber"],
            "site_fa_date": site["first_ascent_date"],
            "is_own_fa": own_fa,
        })
    return pd.DataFrame(rows)
