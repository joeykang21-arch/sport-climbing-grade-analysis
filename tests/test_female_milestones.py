"""Tests for the female ladder.

Unlike the men's milestone tables, this ladder is a curated table rather than a
query over the scrape, so the tests here pin two different things: that the
table is internally well formed, and that the claims it makes which the scrape
*can* check still hold. The second kind is the one that matters — a route
regraded on the site, or an id pointing at the wrong climb, would otherwise
feed a wrong grade straight into the fits.
"""

import pandas as pd
import pytest

from sportgradehistory.female_milestones import (
    FEMALE_MILESTONES,
    MILESTONE_START,
    crosscheck,
    female_ladder,
    ordering_notes,
)
from sportgradehistory.grades import french_ordinal


def test_ladder_is_one_rung_per_grade_with_no_gaps():
    ladder = female_ladder()
    assert len(ladder) == len(FEMALE_MILESTONES)
    # steps run 0..n-1 with no repeated or skipped grade
    assert ladder["steps"].tolist() == list(range(len(ladder)))
    assert ladder["grade"].is_unique
    assert ladder["grade"].iloc[0] == MILESTONE_START
    assert ladder["grade"].iloc[-1] == "9b+"


def test_every_row_carries_a_parseable_grade_and_date():
    ladder = female_ladder()
    assert ladder["ascent"].notna().all()
    assert ladder["grade_order"].notna().all()
    assert set(ladder["date_precision"]) <= {"day", "month", "year"}


def test_coarse_dates_anchor_to_the_start_of_their_period():
    ladder = female_ladder().set_index("grade")
    # year-only -> 1 January; month-only -> the 1st; day -> itself
    assert ladder.loc["8a", "ascent"] == pd.Timestamp("1986-01-01")
    assert ladder.loc["8a+", "ascent"] == pd.Timestamp("1988-03-01")
    assert ladder.loc["9b+", "ascent"] == pd.Timestamp("2025-04-05")


@pytest.mark.parametrize("entry", FEMALE_MILESTONES, ids=lambda e: str(e["grade"]))
def test_each_grade_is_on_the_french_scale(entry):
    assert french_ordinal(str(entry["grade"])) is not None


def test_the_1988_inversion_is_reported_not_silently_fixed():
    """8a+ (Mar 1988) sorts after 8b ("1988" -> 1 Jan) by anchoring alone.

    The ladder must keep grade order and *report* the inversion, because the
    data cannot settle which ascent came first.
    """
    notes = ordering_notes()
    assert len(notes) == 1
    row = notes.iloc[0]
    assert (row["lower_grade"], row["upper_grade"]) == ("8a+", "8b")
    assert bool(row["anchoring_artifact"]) is True


# ── the checks that run against the committed scrape ─────────────────────────

def test_every_route_the_scrape_carries_agrees_on_grade():
    check = crosscheck()
    carried = check[check["grade_agrees"].notna()]
    disagree = carried[~carried["grade_agrees"].astype(bool)]
    assert disagree.empty, (
        "the site's consensus grade has moved away from this table:\n"
        f"{disagree[['grade', 'route', 'site_grade']].to_string(index=False)}"
    )
    # Eight of ten are on the site; Come Back and Choucas are not carried.
    assert len(carried) == 8


def test_excalibur_resolves_by_id_not_by_name():
    """Two climbs are named Excalibur; the 9b+ one is 2384, not the 8c+ 928."""
    check = crosscheck().set_index("grade")
    row = check.loc["9b+"]
    assert row["climb_id"] == 2384
    assert row["site_grade"] == "9b+"
    assert row["site_fa_climber"] == "Stefano Ghisolfi"


def test_the_two_bereziartu_first_ascents_are_flagged_as_her_own():
    check = crosscheck().set_index("grade")
    assert bool(check.loc["8c", "is_own_fa"]) is True
    assert bool(check.loc["8c+", "is_own_fa"]) is True
    # Everything else on the ladder is a repeat of someone else's first ascent.
    others = check.drop(index=["8c", "8c+"])["is_own_fa"].dropna()
    assert not others.any()
