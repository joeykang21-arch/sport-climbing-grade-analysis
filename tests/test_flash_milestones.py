"""Tests for the flash/onsight ladder.

This ladder has two structural features the other two do not — a missing rung at
8a+ and two rungs sharing a date — and both of them are easy to smooth over by
accident. The tests below pin them, because an analysis that reads the rows as
consecutive and evenly spaced would compress a two-grade jump into one and
invent an ordering the record does not have.
"""

import pandas as pd
import pytest

from sportgradehistory.flash_milestones import (
    FLASH_MILESTONES,
    MILESTONE_START,
    crosscheck,
    flash_ladder,
    missing_rungs,
    ordering_notes,
)
from sportgradehistory.grades import french_ordinal


def test_ladder_spans_7b_plus_to_9a_plus():
    ladder = flash_ladder()
    assert len(ladder) == len(FLASH_MILESTONES) == 10
    assert ladder["grade"].iloc[0] == MILESTONE_START == "7b+"
    assert ladder["grade"].iloc[-1] == "9a+"
    assert ladder["grade"].is_unique


def test_steps_are_scale_positions_not_row_numbers():
    """The hole at 8a+ must survive as a gap in ``steps``.

    If these ever become 0..9 consecutively, every interval model downstream
    silently treats the six years from Samizdat to Liaisons Dangereuses as one
    grade step instead of two.
    """
    ladder = flash_ladder().set_index("grade")
    assert ladder.loc["8a", "steps"] == 3
    assert ladder.loc["8b", "steps"] == 5          # not 4: 8a+ is absent
    assert ladder.loc["9a+", "steps"] == 10
    assert flash_ladder()["steps"].tolist() == [0, 1, 2, 3, 5, 6, 7, 8, 9, 10]


def test_the_missing_rung_is_reported():
    assert missing_rungs() == ["8a+"]


def test_the_two_1982_ascents_are_reported_as_an_unresolved_tie():
    notes = ordering_notes()
    assert len(notes) == 1
    row = notes.iloc[0]
    assert (row["lower_grade"], row["upper_grade"]) == ("7b+", "7c")
    assert row["kind"] == "tie"
    assert row["inversion_years"] == 0.0
    assert bool(row["anchoring_artifact"]) is True


def test_coarse_dates_anchor_to_the_start_of_their_period():
    ladder = flash_ladder().set_index("grade")
    assert ladder.loc["7b+", "ascent"] == pd.Timestamp("1982-01-01")
    assert ladder.loc["7c", "ascent"] == pd.Timestamp("1982-01-01")
    assert ladder.loc["9a+", "ascent"] == pd.Timestamp("2018-02-10")


@pytest.mark.parametrize("entry", FLASH_MILESTONES, ids=lambda e: str(e["grade"]))
def test_each_grade_is_on_the_french_scale(entry):
    assert french_ordinal(str(entry["grade"])) is not None


# ── the checks that run against the committed scrape ─────────────────────────

def test_every_route_the_scrape_carries_agrees_on_grade():
    check = crosscheck()
    carried = check[check["grade_agrees"].notna()]
    disagree = carried[~carried["grade_agrees"].astype(bool)]
    assert disagree.empty, (
        "the site's consensus grade has moved away from this table:\n"
        f"{disagree[['grade', 'route', 'site_grade']].to_string(index=False)}"
    )
    # Six of ten are on the site; the four oldest and easiest are not carried.
    assert len(carried) == 6


def test_the_three_self_graded_rungs_are_flagged():
    """Samizdat, Massey Fergusson and Bizi Euskaraz were first ascents.

    Those three milestones were climbed first try on lines nobody had climbed,
    so the grade was proposed by the claimant rather than confirmed first. The
    notebook says so; this pins the flag it says it from.
    """
    check = crosscheck().set_index("grade")
    for grade in ("8a", "8b+", "8c+"):
        assert bool(check.loc[grade, "is_own_fa"]) is True
    for grade in ("8c", "9a", "9a+"):
        assert bool(check.loc[grade, "is_own_fa"]) is False


def test_super_crackinette_predates_its_flash():
    """Ondra flashed a route Megos had established two years earlier."""
    row = crosscheck().set_index("grade").loc["9a+"]
    assert row["climb_id"] == 464
    assert row["site_fa_climber"] == "Alex Megos"
    assert row["site_grade"] == "9a+"
