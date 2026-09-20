"""The hardest-flash/onsight ladder: the first ascent at each grade without falling.

**This ladder mixes two styles, and that is a limitation of the record rather
than a choice made here.**

* **Onsight** — no prior information at all: no beta, no watching anyone else,
  no inspection.
* **Flash** — one attempt, no falls, but beta is allowed.

A flash is the easier of the two, so a ladder that merges them is measuring two
different things with one number. The two were reported separately for most of
this history and have been increasingly blurred in recent years, which is why
they are combined here: separating them would leave two series too short to say
anything about. Read the ladder as **"the hardest grade climbed first try"**,
and read any rung that was a flash rather than an onsight as a lower bound on
what an onsight at that grade would have required. No per-row style label is
recorded in this table, because the source does not reliably carry one.

Like :mod:`sportgradehistory.female_milestones`, this table cannot be derived
from the scrape. A flash or onsight is an ascent *style*, and this snapshot kept
only each climb's first-ascent row — the ascents that define this ladder are
mostly not in the data. The mechanics come from
:mod:`sportgradehistory.ladders`; this module owns the table and its caveats.

**The ladder has a hole at 8a+.** No first flash or onsight of an 8a+ is
recorded, so that rung is absent rather than guessed. ``steps`` is a position on
the French scale, not a row counter, so 8a (step 3) is followed by 8b (step 5)
and the gap is preserved. Anything reading these rows as evenly spaced will
compress a two-grade jump into one.

Run ``python -m sportgradehistory.flash_milestones`` to print the ladder and its
cross-check against the scrape.
"""

from __future__ import annotations

import pandas as pd

from .grades import FRENCH_SCALE, french_ordinal
from . import ladders

# The ladder starts at 7b+, where the recorded flash/onsight history begins.
MILESTONE_START = "7b+"

# Grades inside the ladder's span with no recorded first flash or onsight.
# Reported, never interpolated.
MISSING = {
    "8a+": "no first flash or onsight of an 8a+ is recorded in the source",
}

# Source: the community flash/onsight milestone record, cross-read against this
# repository's scrape via ``climb_id`` where the site carries the route (see
# :func:`crosscheck`).
#
# ``climb_id`` is the climbing-history.org id, used for corroboration only — the
# ascent recorded there is the route's first ascent, which for most of these
# rows is a different ascent by a different climber. ``None`` means the site
# does not carry the route, so that row rests on the external source alone.
FLASH_MILESTONES: list[dict[str, object]] = [
    {
        "grade": "7b+",
        "route": "Captain Crochet",
        "climber": "Patrick Edlinger",
        "crag": "Buoux",
        "country": "FRA",
        "date_raw": "1982",
        "climb_id": None,
    },
    {
        "grade": "7c",
        "route": "La Polka des Ringards",
        "climber": "Patrick Edlinger",
        "crag": "Buoux",
        "country": "FRA",
        "date_raw": "1982",
        "climb_id": None,
    },
    {
        "grade": "7c+",
        "route": "Pol Pot",
        "climber": "Jerry Moffatt",
        "crag": "Verdon Gorge",
        "country": "FRA",
        "date_raw": "1984",
        "climb_id": None,
    },
    {
        "grade": "8a",
        "route": "Samizdat",
        "climber": "Antoine Le Menestrel",
        "crag": "Cimai",
        "country": "FRA",
        "date_raw": "1987",
        # The site records this as his own first ascent, same year.
        "climb_id": 1428,
    },
    # 8a+ is missing here on purpose - see MISSING above.
    {
        "grade": "8b",
        "route": "Liaisons Dangereuses",
        "climber": "Elie Chevieux",
        "crag": "Les Calanques",
        "country": "FRA",
        "date_raw": "1993",
        "climb_id": None,
    },
    {
        "grade": "8b+",
        "route": "Massey Fergusson",
        "climber": "Elie Chevieux",
        "crag": "Calanques",
        "country": "FRA",
        "date_raw": "1995",
        # Site name "Les Massey Ferguson", Luminy (in the Calanques); recorded
        # as his own first ascent, same year.
        "climb_id": 839,
    },
    {
        "grade": "8c",
        "route": "White Zombie",
        "climber": "Yuji Hirayama",
        "crag": "Baltzola",
        "country": "ESP",
        "date_raw": "6th Oct 2004",
        # FA Fernando Martinez, 17 Oct 1996.
        "climb_id": 1313,
    },
    {
        "grade": "8c+",
        "route": "Bizi Euskaraz",
        "climber": "Patxi Usobiaga",
        "crag": "Etxauri",
        "country": "ESP",
        "date_raw": "11th Dec 2007",
        # Site name "Bizi Euskaraz Extension", recorded as his own first
        # ascent on the same day - an onsight of an unclimbed line.
        "climb_id": 1604,
    },
    {
        "grade": "9a",
        "route": "Estado Critico",
        "climber": "Alex Megos",
        "crag": "Siurana",
        "country": "ESP",
        "date_raw": "24th Mar 2013",
        # Site name "Estado Crítico". FA Ramon Julian Puigblanque, 15 Mar 2004.
        "climb_id": 98,
    },
    {
        "grade": "9a+",
        "route": "Super Crackinette",
        "climber": "Adam Ondra",
        "crag": "Saint Leger",
        "country": "FRA",
        "date_raw": "10th Feb 2018",
        # FA Alex Megos, Oct 2016.
        "climb_id": 464,
    },
]


def flash_ladder() -> pd.DataFrame:
    """The flash/onsight ladder as a frame, ordered by grade (with its hole)."""
    return ladders.build_ladder(FLASH_MILESTONES, MILESTONE_START)


def ordering_notes(ladder: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rungs the dates cannot order: here, the two 1982 ascents."""
    return ladders.ordering_notes(flash_ladder() if ladder is None else ladder)


def missing_rungs(ladder: pd.DataFrame | None = None) -> list[str]:
    """Grades in the ladder's span with no recorded ascent."""
    return ladders.missing_rungs(flash_ladder() if ladder is None else ladder,
                                 MILESTONE_START)


def crosscheck(sport: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compare the ladder against the scrape wherever the site carries the route."""
    return ladders.crosscheck(FLASH_MILESTONES, sport)


def main() -> None:
    ladder = flash_ladder()
    base = french_ordinal(MILESTONE_START)
    print(f"-- flash/onsight ladder ({len(ladder)} rungs, {FRENCH_SCALE[base]} .. "
          f"{ladder['grade'].iloc[-1]})")
    print(ladder[["grade", "route", "climber", "ascent", "date_precision",
                  "steps"]].to_string(index=False))

    holes = missing_rungs(ladder)
    print(f"\nmissing rungs: {', '.join(holes) if holes else 'none'}"
          + (f"  ({MISSING.get(holes[0], '')})" if holes else ""))

    print("\n-- cross-check against the scrape")
    check = crosscheck()
    print(check[["grade", "route", "site_name", "site_grade", "grade_agrees",
                 "site_fa_climber", "site_fa_date", "is_own_fa"]]
          .to_string(index=False))
    carried = check["grade_agrees"].notna()
    print(f"\n{int(check.loc[carried, 'grade_agrees'].sum())}/{int(carried.sum())} "
          f"routes carried by the site agree on grade; "
          f"{int((~carried).sum())} not carried at all")

    notes = ordering_notes(ladder)
    if not notes.empty:
        print("\n-- ordering the dates cannot settle")
        print(notes.to_string(index=False))


if __name__ == "__main__":
    main()
