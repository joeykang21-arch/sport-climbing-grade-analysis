"""The female sport climbing ladder: the first woman at each new top grade.

**This table is not derived from the scrape, and it cannot be.** Every other
milestone table in this repository is computed from
``data/processed/sport_routes.csv`` at call time, with the seed lists used only
as reconciliation targets. Two properties of the data make that impossible
here:

* ``climbs_detail.csv`` carries no gender field, and nothing in the scrape
  implies one.
* A female "first at grade" is almost always a **repeat**, not a first ascent,
  and this scrape kept only the first ascent row per climb (HANDOFF.md). The
  ascents that define this ladder are exactly the rows the scrape does not
  have.

So ``FEMALE_MILESTONES`` below is a curated table with an external source, in
the spirit of ``FA_SUPPLEMENTS`` in :mod:`sportgradehistory.milestones` — and
like those supplements it is cross-checked against the scrape wherever the
scrape can speak. :func:`crosscheck` does that check: it matches each route to
its ``climb_id`` and compares the milestone grade against the site's consensus
grade, so a wrong grade in this table shows up as a disagreement rather than
propagating silently into a fit.

The two conventions that split the men's ladder (``as_proposed`` /
``as_consensus``) do not apply here. A female ascent is dated years to decades
after the route's first ascent, by which time the grade is the consensus
grade; "the grade it was given at its FA" is a statement about the (male) first
ascentionist, not about the woman repeating it. This ladder is therefore
single-convention, and it is the consensus one.

Run ``python -m sportgradehistory.female_milestones`` to print the ladder and
its cross-check against the scrape.
"""

from __future__ import annotations

import pandas as pd

from . import ladders
from .grades import FRENCH_SCALE, french_ordinal

# The ladder is tracked from 8a, where the female record begins. The men's
# table starts one notch higher (8a+, The Face, 1983) because that is where
# its own record begins; neither start is a claim about the other.
MILESTONE_START = "8a"

# Source for every row: Wikipedia, "List of first female ascents (sport
# climbing)" and "List of grade milestones in rock climbing", cross-read
# against this repository's scrape via ``climb_id`` where the site carries the
# route (see :func:`crosscheck`).
#
# ``climb_id`` is the climbing-history.org id, used for corroboration only —
# the ascent recorded there is the route's first ascent, not the female one.
# ``None`` means the site does not carry the route at all, so the grade in
# that row stands on the external source alone.
FEMALE_MILESTONES: list[dict[str, object]] = [
    {
        "grade": "8a",
        "route": "Come Back",
        "climber": "Luisa Iovane",
        "crag": "Val San Nicolo",
        "country": "ITA",
        "date_raw": "1986",
        "climb_id": None,
    },
    {
        "grade": "8a+",
        "route": "Choucas",
        "climber": "Catherine Destivelle",
        "crag": "Buoux",
        "country": "FRA",
        "date_raw": "Mar 1988",
        "climb_id": None,
    },
    {
        "grade": "8b",
        "route": "Sortileges",
        "climber": "Isabelle Patissier",
        "crag": "Le Cimai",
        "country": "FRA",
        "date_raw": "1988",
        # Site spelling "Sortilleges", Cimai. FA J-B Tribout, 30 Apr 1986.
        "climb_id": 1586,
    },
    {
        "grade": "8b+",
        "route": "Masse Critique",
        "climber": "Lynn Hill",
        "crag": "Cimai",
        "country": "FRA",
        "date_raw": "1990",
        # FA J-B Tribout, 10 Dec 1989 - Hill's ascent is the first repeat.
        "climb_id": 1429,
    },
    {
        "grade": "8c",
        "route": "Honky Tonky",
        "climber": "Josune Bereziartu",
        "crag": "Onate",
        "country": "ESP",
        "date_raw": "May 1998",
        # Bereziartu's own first ascent; the site dates it Apr 1998.
        "climb_id": 1304,
    },
    {
        "grade": "8c+",
        "route": "Honky Tonk Mix",
        "climber": "Josune Bereziartu",
        "crag": "Onate",
        "country": "ESP",
        "date_raw": "Jun 2000",
        # Site name "Honky Mix"; her own FA, dated 30 Jun 2000 there.
        "climb_id": 862,
    },
    {
        "grade": "9a",
        "route": "Bain de Sang",
        "climber": "Josune Bereziartu",
        "crag": "Saint Loup",
        "country": "SUI",
        "date_raw": "29th Oct 2002",
        # FA Fred Nicole, Sep 1993.
        "climb_id": 517,
    },
    {
        "grade": "9a+",
        "route": "La Rambla",
        "climber": "Margo Hayes",
        "crag": "Siurana",
        "country": "ESP",
        "date_raw": "26th Feb 2017",
        # FA (extension) Ramon Julian Puigblanque, 8 Mar 2003.
        "climb_id": 514,
    },
    {
        "grade": "9b",
        "route": "La Planta de Shiva",
        "climber": "Angela Eiter",
        "crag": "Villanueva del Rosario",
        "country": "ESP",
        "date_raw": "22nd Oct 2017",
        # FA Adam Ondra, 7 Apr 2011.
        "climb_id": 492,
    },
    {
        "grade": "9b+",
        "route": "Excalibur",
        "climber": "Brooke Raboutou",
        "crag": "Arco",
        "country": "ITA",
        "date_raw": "5th Apr 2025",
        # FA Stefano Ghisolfi, 3 Feb 2023. Note climb 928 is a different
        # Excalibur (8c+, James Pearson) - match on the id, never the name.
        "climb_id": 2384,
    },
]


def female_ladder() -> pd.DataFrame:
    """The female milestone ladder as a frame, ordered by grade.

    Mechanics in :func:`sportgradehistory.ladders.build_ladder`; this ladder is
    gapless, every rung from 8a to 9b+ being recorded.
    """
    return ladders.build_ladder(FEMALE_MILESTONES, MILESTONE_START)


def ordering_notes(ladder: pd.DataFrame | None = None) -> pd.DataFrame:
    """Consecutive rungs whose dates do not order the way the grades do.

    Here that is the 1988 pair: Choucas (8a+, March) against Sortileges (8b,
    year-only, so anchored to 1 January and sorting ahead of it).
    """
    return ladders.ordering_notes(female_ladder() if ladder is None else ladder)


def crosscheck(sport: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compare every row of the ladder against the scrape, where it can."""
    return ladders.crosscheck(FEMALE_MILESTONES, sport)


def main() -> None:
    ladder = female_ladder()
    base = french_ordinal(MILESTONE_START)
    print(f"-- female ladder ({len(ladder)} rungs, {FRENCH_SCALE[base]} .. "
          f"{ladder['grade'].iloc[-1]})")
    print(ladder[["grade", "route", "climber", "ascent", "date_precision",
                  "steps"]].to_string(index=False))

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
