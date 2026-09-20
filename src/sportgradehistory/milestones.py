"""Milestone tables: the first route at each new top sport grade.

"First at grade" is ambiguous in sport climbing, and this module does not pick
a side. Every table is produced under an explicit ``GRADING_CONVENTION``:

``as_proposed``
    The grade the route was given at the time of its first ascent — the
    sport's contemporaneous belief about its own ceiling. Reconstructed from
    ``first_suggested_grade`` where the site records one, else the current
    grade (i.e. a route with no recorded suggestion is assumed unregraded;
    ``regraded_routes.csv`` bounds how wrong that can be).

``as_consensus``
    The grade the route holds today after repeats. Retrospective, and it
    rewrites history: Hubble moves from the first 8c+ to the first 9a, Liquid
    Ambar inherits 8c+, Open Air takes 9a+ five years before Realization.

Neither milestone list is hardcoded — both are derived from
``data/processed/sport_routes.csv`` at call time. The seed lists at the bottom
of this module are **reconciliation targets only**, used to report
disagreements, never as a data source.

Three curated tables patch known holes in the scrape, each entry cited:

* ``TIE_BREAKS`` resolves same-year ties the dates cannot settle, where a
  year-only date anchored to 1 January would otherwise decide a milestone by
  artifact. Applied only where :func:`_ordering_unresolved` agrees the data
  cannot order the pair; the losing rival is still reported.
* ``FA_SUPPLEMENTS`` fills first-ascent fields for rows the site renders
  without them (its pages omit the ascent list when the chronologically first
  entry is an unsuccessful attempt — HANDOFF.md item 1). Applied only where
  the scraped field is empty; the scrape always wins where it has data.
* ``DISPUTED_CLAIMS`` names the claimed-but-unconfirmed ascents that a naive
  "first at grade" query must not surface silently: Akira and Chilam Balam.
  Milestone tables exclude them by default and can include them on request,
  so the reader can see exactly what accepting a claim would do.

Run ``python -m sportgradehistory.milestones`` to write
``data/processed/disputed_ascents.csv`` and print both milestone tables with
their seed reconciliation.
"""

from __future__ import annotations

import re

import pandas as pd

from . import config
from .grades import FRENCH_SCALE, clean_grade, french_ordinal

GRADING_CONVENTIONS = ("as_proposed", "as_consensus")

# Milestones are tracked from 8a+ (The Face, 1983) upward; the history below
# that point predates sport climbing as a discipline.
MILESTONE_START = "8a+"

# ── Curated patches, each cited ──────────────────────────────────────────────

# First-ascent fields for rows where the site's HTML omits the ascent list
# entirely (HANDOFF.md, "Looked wrong" item 1). Filled from the cited source;
# only fields the scrape left empty are ever taken from here.
FA_SUPPLEMENTS: dict[int, dict[str, str]] = {
    # Punks in the Gym: 12 recorded ascents, none rendered. Wikipedia's grade
    # milestone list gives climber and year only, so date precision is "year".
    519: {
        "first_climber": "Wolfgang Güllich",
        "first_ascent_date": "1985",
        "supplement_source": "Wikipedia: List of grade milestones in rock climbing (year only)",
    },
    # B.I.G: one recorded ascent, rendered only as Adam Ondra's ongoing
    # attempts. Wikipedia dates Schubert's FA to the day.
    2734: {
        "first_climber": "Jakob Schubert",
        "first_ascent_date": "20th Sep 2023",
        "supplement_source": "Wikipedia: List of grade milestones in rock climbing",
    },
}

# Same-year ties the dates cannot separate, resolved by hand and applied to
# both conventions. A year-only date parses to 1 January, so it sorts ahead of
# every dated rival in its year — an artifact of anchoring, not evidence of
# being first. Where that artifact would decide a milestone, the entry below
# names the route that takes the slot; the rival is still reported in
# ``ordering_unresolved_with``, so nothing downstream pretends it is settled.
TIE_BREAKS: dict[str, dict[str, object]] = {
    # 8b, both conventions. The scrape dates Les Mains Sales to "1984" (year
    # only) and Kanal im Rücken to 24 Oct 1984. Wikipedia's grade-milestone
    # list and this module's own seed lists both name Kanal im Rücken as the
    # first 8b, so the dated route takes the slot.
    "8b": {
        "climb_id": 521,
        "note": (
            "Kanal im Rücken, 24 Oct 1984 (dated); Les Mains Sales is year-only "
            "1984 and only sorts first because it anchors to 1 January."
        ),
    },
}

# Claimed-but-unconfirmed ascents. The site itself does not carry these claims
# as consensus (Akira is recorded at 9a with the 9b suggestion preserved;
# Chilam Balam's 2003 FA is classed "dnf" in the site's own ascent table), so
# the claims below are what the *claim* said, for the with-disputed variant.
DISPUTED_CLAIMS: dict[int, dict[str, str]] = {
    475: {
        "claimed_grade": "9b",
        "claimed_climber": "Fred Rouhling",
        "claimed_date": "6th Jun 1995",
        "claim_note": (
            "Claimed 9b in 1995, 17 years before Change. Never accepted; the "
            "site carries Akira at 9a consensus with Rouhling's 9b suggestion "
            "recorded, and its 4 logged ascents are at the consensus grade."
        ),
    },
    789: {
        "claimed_grade": "9b+",
        "claimed_climber": "Bernabé Fernández",
        "claimed_date": "4th Jul 2003",
        "claim_note": (
            "Claimed 9b+ in 2003, 9 years before Change. The site classes the "
            "FA as not-successful (dnf) in its ascent table and carries the "
            "route at 9a+ from its 11 later ascents."
        ),
    },
}

_YEAR_ONLY = re.compile(r"^\s*\d{4}\s*$")
_MONTH_ONLY = re.compile(r"^\s*[A-Za-z]+\s+\d{4}\s*$")
_BEFORE = re.compile(r"^\s*before\b", re.IGNORECASE)


def date_precision(raw: object) -> str | None:
    """How much of ``first_ascent_date`` is real: day, month, year or bound.

    The parsed ``first_ascent`` anchors coarse dates to the start of their
    period, so a claim like "weeks apart" must check this first.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or pd.isna(raw):
        return None
    text = str(raw).strip()
    if not text:
        return None
    if _BEFORE.match(text):
        return "upper-bound"
    if _YEAR_ONLY.match(text):
        return "year"
    if _MONTH_ONLY.match(text):
        return "month"
    return "day"


def load_sport(
    path=None,
    single_pitch_only: bool = True,
) -> pd.DataFrame:
    """Load ``sport_routes.csv`` and attach the milestone-analysis columns.

    Adds ``proposed_clean``/``proposed_order`` (the as_proposed grade),
    ``date_precision``, ``status`` and the supplement/claim annotations, and
    drops the site's duplicate entries (same name, location and FA date under
    two climb ids — e.g. Biographie appears as both 513 and 7816), keeping the
    lower id and recording the drop in ``duplicate_of``... the dropped rows are
    simply removed; the survivor keeps its own id.
    """
    df = pd.read_csv(path or config.SPORT_CSV, encoding="utf-8")

    if single_pitch_only:
        df = df[~df["is_multipitch"].astype(bool)]

    # The site occasionally carries the same route twice; an identical
    # (name, location, FA date) triple is the same physical route.
    df = df.sort_values("climb_id", kind="stable").drop_duplicates(
        subset=["climb_name", "location", "first_ascent_date"], keep="first"
    )

    df = df.copy()

    # Patch the rendering holes, scrape-first.
    df["supplement_source"] = pd.NA
    for climb_id, patch in FA_SUPPLEMENTS.items():
        mask = df["climb_id"] == climb_id
        if not mask.any():
            continue
        for field in ("first_climber", "first_ascent_date"):
            need = mask & df[field].isna()
            df.loc[need, field] = patch[field]
            df.loc[need, "supplement_source"] = patch["supplement_source"]

    # Re-derive the parsed date so supplemented rows get one too.
    from .grades import parse_ascent_date

    df["first_ascent"] = pd.to_datetime(
        df["first_ascent_date"].map(parse_ascent_date), errors="coerce"
    )
    df["first_ascent_year"] = df["first_ascent"].dt.year.astype("Int64")
    df["date_precision"] = df["first_ascent_date"].map(date_precision)

    # The as_proposed grade: the FA-ist's recorded suggestion where the site
    # has one on the French scale, else today's grade (assumed unregraded).
    suggested = df["first_suggested_grade"].map(clean_grade)
    suggested_order = df["first_suggested_grade"].map(french_ordinal)
    has_suggestion = suggested_order.notna()
    df["proposed_clean"] = df["grade_clean"].where(~has_suggestion, suggested)
    df["proposed_order"] = df["grade_order"].where(~has_suggestion, suggested_order)
    df["proposed_is_reconstructed"] = has_suggestion

    # Status, most severe label wins: disputed > regraded > unrepeated.
    df["status"] = "consensus"
    df.loc[df["num_ascents"] <= 1, "status"] = "unrepeated"
    df.loc[has_suggestion & (suggested_order != df["grade_order"]), "status"] = "regraded"
    df.loc[df["climb_id"].isin(DISPUTED_CLAIMS), "status"] = "disputed"

    for field in ("claimed_grade", "claimed_climber", "claimed_date", "claim_note"):
        df[field] = df["climb_id"].map(
            {cid: patch[field] for cid, patch in DISPUTED_CLAIMS.items()}
        )

    return df.reset_index(drop=True)


def _ordering_unresolved(chosen: pd.Series, rival: pd.Series) -> bool:
    """Whether the data can actually order two same-grade candidates.

    Year-only dates are anchored to 1 January by ``parse_ascent_date``, so a
    year-only candidate "preceding" a dated one is an artifact, not a fact.
    The ordering counts as resolved only when both dates are of day or month
    precision and do not collide at that precision.
    """
    a, b = chosen["first_ascent"], rival["first_ascent"]
    if pd.isna(a) or pd.isna(b):
        return True
    if a.year != b.year:
        return False
    pa, pb = chosen["date_precision"], rival["date_precision"]
    if pa not in ("day", "month") or pb not in ("day", "month"):
        return True  # a year-only or "Before" date in the same year
    if a.month == b.month and ("month" in (pa, pb) or a == b):
        return True  # same month and at least one date no finer than the month
    return False


def _convention_columns(convention: str) -> tuple[str, str]:
    if convention == "as_proposed":
        return "proposed_clean", "proposed_order"
    if convention == "as_consensus":
        return "grade_clean", "grade_order"
    raise ValueError(f"convention must be one of {GRADING_CONVENTIONS}, got {convention!r}")


def milestone_table(
    sport: pd.DataFrame,
    convention: str,
    include_disputed: bool = False,
    start: str = MILESTONE_START,
) -> pd.DataFrame:
    """The first route at each grade from ``start`` up, under ``convention``.

    Disputed claims are excluded unless asked for; when included, a disputed
    route competes at its **claimed** grade and date, since that is the claim
    being entertained. Routes with no parseable FA date cannot be "first" and
    are skipped (they are few and none is a candidate — HANDOFF.md item 5).
    """
    grade_col, order_col = _convention_columns(convention)

    frame = sport.copy()
    if include_disputed:
        claimed_order = frame["claimed_grade"].map(french_ordinal)
        claimed = frame["status"].eq("disputed") & claimed_order.notna()
        frame.loc[claimed, grade_col] = frame.loc[claimed, "claimed_grade"]
        frame.loc[claimed, order_col] = claimed_order[claimed]
        from .grades import parse_ascent_date

        frame.loc[claimed, "first_ascent"] = pd.to_datetime(
            frame.loc[claimed, "claimed_date"].map(parse_ascent_date), errors="coerce"
        )
        frame.loc[claimed, "date_precision"] = frame.loc[claimed, "claimed_date"].map(
            date_precision
        )
        # The claim is the FA being entertained, so its claimant is the
        # climber -- the scraped field can be empty when the site classes the
        # claimed ascent as unsuccessful (Chilam Balam).
        frame.loc[claimed, "first_climber"] = frame.loc[claimed, "claimed_climber"]
    else:
        frame = frame[frame["status"] != "disputed"]

    cutoff = french_ordinal(start)
    frame = frame[frame[order_col].notna() & (frame[order_col] >= cutoff)]
    frame = frame[frame["first_ascent"].notna()]

    rows = []
    for ordinal in sorted(frame[order_col].unique()):
        at_grade = frame[frame[order_col] == ordinal]
        first = at_grade.sort_values(
            ["first_ascent", "climb_id"], kind="stable"
        ).iloc[0]

        # A curated tie-break may take the slot from the anchored-date winner,
        # but only where the data genuinely cannot order the two: overriding a
        # resolved ordering would be discarding evidence, not an artifact.
        tie_break = TIE_BREAKS.get(FRENCH_SCALE[int(ordinal)])
        if tie_break is not None:
            preferred = at_grade[at_grade["climb_id"] == tie_break["climb_id"]]
            if (
                not preferred.empty
                and preferred.iloc[0]["climb_id"] != first["climb_id"]
                and _ordering_unresolved(first, preferred.iloc[0])
            ):
                first = preferred.iloc[0]

        # Same-year rivals the dates cannot actually separate. The winner
        # above is the anchored-date ordering, which for year-only dates is
        # an artifact -- so the rivals are named rather than suppressed, and
        # nothing downstream may pretend the ordering is settled.
        rivals = [
            f"{r['climb_name']} ({r['first_climber']}, {r['first_ascent_date']})"
            for _, r in at_grade.iterrows()
            if r["climb_id"] != first["climb_id"] and _ordering_unresolved(first, r)
        ]

        rows.append(
            {
                "convention": convention,
                "grade": FRENCH_SCALE[int(ordinal)],
                "grade_order": int(ordinal),
                "climb_id": first["climb_id"],
                "route": first["climb_name"],
                "climber": first["first_climber"],
                "first_ascent": first["first_ascent"],
                "date_precision": first["date_precision"],
                "location": first["location"],
                "num_ascents": first["num_ascents"],
                "status": first["status"],
                "grade_today": first["grade_clean"],
                "grade_at_fa": first["proposed_clean"],
                "supplement_source": first["supplement_source"],
                "n_routes_at_grade": len(at_grade),
                "ordering_unresolved_with": "; ".join(rivals) if rivals else pd.NA,
            }
        )

    return pd.DataFrame(rows)


def breakthrough_table(
    sport: pd.DataFrame,
    convention: str,
    include_disputed: bool = False,
    start: str = MILESTONE_START,
) -> pd.DataFrame:
    """When the *ceiling* first reached each grade: earliest FA at or above it.

    Usually identical to :func:`milestone_table`; it differs only if some
    grade's first route postdates a harder route (a grade filled in late). The
    regression notebooks fit these dates, because "the ceiling rose to g" is
    the event the progression story is about.
    """
    milestones = milestone_table(sport, convention, include_disputed, start)
    if milestones.empty:
        return milestones

    out = milestones.copy()
    # Walking down from the top grade, the breakthrough date can never be
    # later than the breakthrough of any harder grade.
    for i in range(len(out) - 2, -1, -1):
        later = out.iloc[i + 1]
        if pd.notna(later["first_ascent"]) and later["first_ascent"] < out.iloc[i]["first_ascent"]:
            for col in (
                "climb_id", "route", "climber", "first_ascent", "date_precision",
                "location", "num_ascents", "status", "grade_today", "grade_at_fa",
                "supplement_source",
            ):
                out.iloc[i, out.columns.get_loc(col)] = later[col]
    return out


def disputed_ascents(sport: pd.DataFrame, floor: str = "9a+") -> pd.DataFrame:
    """The top-end status audit written to ``disputed_ascents.csv``.

    Every route whose grade under *either* convention — or whose claimed grade
    — reaches ``floor``, with its status (consensus / disputed / unrepeated /
    regraded) and the claim metadata where there is one. This is the table
    that keeps a naive "first at grade" query honest.
    """
    cutoff = french_ordinal(floor)
    claimed_order = sport["claimed_grade"].map(french_ordinal)
    keep = (
        (sport["grade_order"] >= cutoff)
        | (sport["proposed_order"] >= cutoff)
        | (claimed_order >= cutoff)
    )

    columns = [
        "climb_id", "climb_name", "location", "grade_clean", "proposed_clean",
        "claimed_grade", "status", "first_climber", "first_ascent_date",
        "date_precision", "first_ascent_year", "num_ascents",
        "first_suggested_grade", "is_multipitch", "supplement_source",
        "claimed_climber", "claimed_date", "claim_note", "climb_url",
    ]
    out = sport.loc[keep, columns].copy()
    out["_order"] = sport.loc[keep, "grade_order"]
    out = out.sort_values(
        ["_order", "first_ascent_year"], ascending=[False, True], kind="stable"
    ).drop(columns="_order")
    return out.reset_index(drop=True)


# ── Reconciliation seeds (targets to check against, never a data source) ─────

SEED_AS_PROPOSED = [
    ("8a+", 1983, "The Face", "Jerry Moffatt"),
    ("8b", 1984, "Kanal im Rücken", "Wolfgang Güllich"),
    ("8b+", 1985, "Punks in the Gym", "Wolfgang Güllich"),
    ("8c", 1987, "Wallstreet", "Wolfgang Güllich"),
    ("8c+", 1990, "Hubble", "Ben Moon"),
    ("9a", 1991, "Action Directe", "Wolfgang Güllich"),
    ("9a+", 2001, "Realization", "Chris Sharma"),
    ("9b", 2008, "Jumbo Love", "Chris Sharma"),
    ("9b+", 2012, "Change", "Adam Ondra"),
    ("9c", 2017, "Silence", "Adam Ondra"),
]

# Only the rows expected to differ from as_proposed.
SEED_AS_CONSENSUS_OVERRIDES = [
    ("8c+", 1990, "Liquid Ambar", "Jerry Moffatt"),
    ("9a", 1990, "Hubble", "Ben Moon"),
    ("9a+", 1996, "Open Air", "Alexander Huber"),
]

SEED_AS_CONSENSUS = [
    override
    if (override := next((o for o in SEED_AS_CONSENSUS_OVERRIDES if o[0] == row[0]), None))
    else row
    for row in SEED_AS_PROPOSED
]


def reconcile(milestones: pd.DataFrame, seeds: list[tuple]) -> pd.DataFrame:
    """Compare a computed milestone table against a seed list, row by row.

    Returns one row per seed grade with the computed counterpart and an
    ``agrees`` verdict (route match and FA year match). Routes are matched
    loosely on name so "Biographie" satisfies a "Realization" seed — the two
    names label one route — with the alias noted rather than hidden.
    """
    aliases = {"realization": ["biographie"], "wallstreet": ["wall street"]}

    rows = []
    for grade, year, route, climber in seeds:
        got = milestones[milestones["grade"] == grade]
        if got.empty:
            rows.append(
                {"grade": grade, "seed_route": route, "seed_year": year,
                 "found_route": None, "found_year": None, "found_climber": None,
                 "agrees": False, "note": "no route at this grade in the data"}
            )
            continue
        found = got.iloc[0]
        found_year = found["first_ascent"].year if pd.notna(found["first_ascent"]) else None

        seed_key = route.lower()
        found_key = str(found["route"]).lower()
        name_match = seed_key in found_key or found_key in seed_key
        alias_used = None
        if not name_match:
            for canonical, alts in aliases.items():
                keys = [canonical, *alts]
                if any(k in seed_key for k in keys) and any(k in found_key for k in keys):
                    name_match, alias_used = True, f"{route} = {found['route']}"
                    break

        rows.append(
            {
                "grade": grade,
                "seed_route": route,
                "seed_year": year,
                "found_route": found["route"],
                "found_year": found_year,
                "found_climber": found["climber"],
                "agrees": bool(name_match and found_year == year),
                "note": alias_used or ("" if name_match else "different route"),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    sport = load_sport()

    disputed = disputed_ascents(sport)
    config.DISPUTED_ASCENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    disputed.to_csv(config.DISPUTED_ASCENTS_CSV, index=False, encoding="utf-8")
    disputed.to_excel(config.DISPUTED_ASCENTS_CSV.with_suffix(".xlsx"), index=False)
    print(f"wrote {config.DISPUTED_ASCENTS_CSV.name}: {len(disputed)} rows")
    print(disputed["status"].value_counts().to_string(), end="\n\n")

    for convention, seeds in (
        ("as_proposed", SEED_AS_PROPOSED),
        ("as_consensus", SEED_AS_CONSENSUS),
    ):
        table = milestone_table(sport, convention)
        merged = reconcile(table, seeds)
        print(f"── {convention} " + "─" * 40)
        show = table[["grade", "route", "climber", "first_ascent", "date_precision", "status"]]
        print(show.to_string(index=False))
        disagreements = merged[~merged["agrees"]]
        if disagreements.empty:
            print("seed reconciliation: all agree\n")
        else:
            print("seed disagreements:")
            print(disagreements.to_string(index=False), end="\n\n")


if __name__ == "__main__":
    main()
