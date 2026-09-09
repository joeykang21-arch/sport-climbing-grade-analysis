"""Tests for the milestone machinery: conventions, disputes, unresolved ties.

These run on synthetic frames shaped like ``sport_routes.csv``, so they pin
behaviour without depending on the committed data. One integration test at the
bottom runs on the real file and pins the headline milestones of this
snapshot; if a rebuild from new data moves them, that is a finding, and the
test failing is the alarm going off.
"""

import pandas as pd
import pytest

from sportgradehistory import config
from sportgradehistory.milestones import (
    GRADING_CONVENTIONS,
    date_precision,
    load_sport,
    milestone_table,
)


def _sport_frame(rows):
    columns = [
        "climb_id", "climb_name", "location", "grade_clean", "grade_order",
        "first_suggested_grade", "first_ascent_date", "first_climber",
        "num_ascents", "is_multipitch",
    ]
    df = pd.DataFrame(rows, columns=columns)
    # The columns load_sport would have inherited from sport_routes.csv,
    # including the precomputed French ordinal build_datasets writes.
    from sportgradehistory.grades import french_ordinal

    df["grade"] = df["grade_clean"]
    df["grade_order"] = df["grade_clean"].map(french_ordinal)
    df["climb_url"] = ""
    df["first_style"] = None
    return df


def _prepare(df, tmp_path):
    path = tmp_path / "sport_routes.csv"
    df.to_csv(path, index=False)
    return load_sport(path=path)


FRAME = [
    # id, name, location, grade_clean, grade_order(ignored by load), suggestion,
    # date, climber, ascents, multipitch
    (1, "Old Consensus", "A", "8c", None, None, "1987", "Someone", 10, False),
    (2, "Proposed Softer", "B", "9a", None, "8c+", "14th Jun 1990", "B. Moon", 12, False),
    (3, "Late Harder", "C", "9a", None, None, "14th Sep 1991", "W. Gullich", 30, False),
    (4, "The Claim", "D", "9a", None, "9b", "6th Jun 1995", "F. Rouhling", 4, False),
    (5, "Year Only", "E", "9a+", None, None, "1996", "S. Furst", 5, False),
    (6, "December Dated", "E", "9a+", None, "9a", "6th Dec 1996", "A. Huber", 2, False),
    (7, "Unrepeated Top", "F", "9c", None, "9c", "3rd Sep 2017", "A. Ondra", 1, False),
    (8, "A Multipitch", "G", "8c", None, None, "1999", "Someone", 3, True),
]


def test_rejects_unknown_convention(tmp_path):
    sport = _prepare(_sport_frame(FRAME), tmp_path)
    with pytest.raises(ValueError):
        milestone_table(sport, "as_wikipedia")
    assert set(GRADING_CONVENTIONS) == {"as_proposed", "as_consensus"}


def test_conventions_disagree_exactly_where_the_suggestion_does(tmp_path):
    sport = _prepare(_sport_frame(FRAME), tmp_path)

    consensus = milestone_table(sport, "as_consensus").set_index("grade")
    proposed = milestone_table(sport, "as_proposed").set_index("grade")

    # Under consensus, route 2 is a 9a from 1990 and takes the grade.
    assert consensus.loc["9a", "route"] == "Proposed Softer"
    # Under the proposal, it was an 8c+ -- so 9a falls to the 1991 route.
    assert proposed.loc["8c+", "route"] == "Proposed Softer"
    assert proposed.loc["9a", "route"] == "Late Harder"


def test_disputed_claims_are_excluded_then_included_at_claimed_grade(tmp_path):
    # Route 4 mimics Akira: consensus 9a, suggested 9b, disputed by id.
    from sportgradehistory import milestones as m

    original = m.DISPUTED_CLAIMS
    m.DISPUTED_CLAIMS = {
        4: {
            "claimed_grade": "9b",
            "claimed_climber": "F. Rouhling",
            "claimed_date": "6th Jun 1995",
            "claim_note": "test",
        }
    }
    try:
        sport = _prepare(_sport_frame(FRAME), tmp_path)

        without = milestone_table(sport, "as_proposed")
        assert "9b" not in set(without["grade"])
        assert "The Claim" not in set(without["route"])

        with_claims = milestone_table(
            sport, "as_proposed", include_disputed=True
        ).set_index("grade")
        assert with_claims.loc["9b", "route"] == "The Claim"
        assert with_claims.loc["9b", "status"] == "disputed"
        assert with_claims.loc["9b", "first_ascent"].year == 1995
    finally:
        m.DISPUTED_CLAIMS = original


def test_same_year_tie_is_flagged_not_guessed(tmp_path):
    sport = _prepare(_sport_frame(FRAME), tmp_path)
    consensus = milestone_table(sport, "as_consensus").set_index("grade")

    # The year-only 1996 route anchors to 1 January and "wins", but the data
    # cannot actually order it against the 6 Dec 1996 route.
    row = consensus.loc["9a+"]
    assert row["route"] == "Year Only"
    assert row["date_precision"] == "year"
    assert "December Dated" in row["ordering_unresolved_with"]

    # A genuinely dated pair in different years is not flagged.
    assert pd.isna(consensus.loc["9a", "ordering_unresolved_with"])


def test_single_pitch_only_default_drops_multipitch(tmp_path):
    df = _sport_frame(FRAME)
    path = tmp_path / "sport_routes.csv"
    df.to_csv(path, index=False)

    assert "A Multipitch" not in set(load_sport(path=path)["climb_name"])
    kept = load_sport(path=path, single_pitch_only=False)
    assert "A Multipitch" in set(kept["climb_name"])


def test_status_ladder(tmp_path, monkeypatch):
    from sportgradehistory import milestones as m

    monkeypatch.setattr(
        m,
        "DISPUTED_CLAIMS",
        {4: {"claimed_grade": "9b", "claimed_climber": "F. Rouhling",
             "claimed_date": "6th Jun 1995", "claim_note": "test"}},
    )
    sport = _prepare(_sport_frame(FRAME), tmp_path).set_index("climb_id")
    assert sport.loc[1, "status"] == "consensus"
    assert sport.loc[2, "status"] == "regraded"    # suggestion != consensus
    assert sport.loc[4, "status"] == "disputed"    # curated claim wins the label
    assert sport.loc[7, "status"] == "unrepeated"  # one ascent, no regrade


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4th Jun 2017", "day"),
        ("Jul 1998", "month"),
        ("1990", "year"),
        ("Before Jan 1995", "upper-bound"),
        (None, None),
    ],
)
def test_date_precision(raw, expected):
    assert date_precision(raw) == expected


@pytest.mark.skipif(
    not config.SPORT_CSV.exists(), reason="processed data not built"
)
def test_this_snapshots_headline_milestones():
    """Pin the 2026-09-09 snapshot's milestones; a move on rebuild is a finding."""
    sport = load_sport()

    consensus = milestone_table(sport, "as_consensus").set_index("grade")
    assert consensus.loc["8c+", "route"] == "Liquid Ambar"
    assert consensus.loc["9a", "route"] == "Hubble"
    assert consensus.loc["9b", "route"] == "Jumbo Love"
    assert consensus.loc["9c", "route"] == "Silence"
    # Qui vs Open Air is unresolved in the data, and must say so.
    assert not pd.isna(consensus.loc["9a+", "ordering_unresolved_with"])

    proposed = milestone_table(sport, "as_proposed").set_index("grade")
    assert proposed.loc["8c+", "route"] == "Hubble"
    assert proposed.loc["9b", "route"] == "Ali Hulk (extension sit start)"

    with_claims = milestone_table(
        sport, "as_proposed", include_disputed=True
    ).set_index("grade")
    assert with_claims.loc["9b", "route"] == "Akira"
    assert with_claims.loc["9b+", "route"] == "Chilam Balam"
    assert with_claims.loc["9b+", "climber"] == "Bernabé Fernández"
