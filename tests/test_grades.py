"""Tests for grade normalisation, scale ordering and ascent-date parsing."""

import pandas as pd
import pytest

from sportgradehistory.grades import (
    FONT_SCALE,
    FRENCH_SCALE,
    clean_grade,
    font_ordinal,
    font_to_v,
    french_ordinal,
    french_to_yds,
    is_french_grade,
    parse_ascent_date,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("9a/9a+", "9a"),       # slash pairs collapse to the lower grade
        ("8C+/9b", "8C+"),
        ("(approx) 7A", "7A"),
        ("8c (soft)", "8c"),
        ("8B (soft)", "8B"),
        ("8C (hard)", "8C"),
        ("  8a+  ", "8a+"),
        ("9a", "9a"),           # case is meaningful and must survive
        ("", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_clean_grade(raw, expected):
    assert clean_grade(raw) == expected


# ── French sport scale ────────────────────────────────────────────────────────


def test_french_scale_orders_numerically_not_lexically():
    # The defect this replaces: string sorting puts "10" before "3" and "7a"
    # after "8c".
    assert french_ordinal("5a") < french_ordinal("7a") < french_ordinal("8a") < french_ordinal("9c")


def test_french_scale_is_strictly_increasing():
    ordinals = [french_ordinal(g) for g in FRENCH_SCALE]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)


def test_french_ordinal_slash_and_qualifier_grades():
    # The forms consensus-uncertain sport grades actually take on the site.
    assert french_ordinal("9a/9a+") == french_ordinal("9a")
    assert french_ordinal("8c (soft)") == french_ordinal("8c")
    assert french_ordinal("(approx) 8b") == french_ordinal("8b")


def test_french_ordinal_ignores_case():
    # Sport grades are recorded lower-case, but not perfectly consistently.
    assert french_ordinal("8A") == french_ordinal("8a")


def test_french_ordinal_rejects_off_scale_grades():
    assert french_ordinal("E8") is None       # UK trad
    assert french_ordinal("5.14d") is None    # YDS
    assert french_ordinal("Mt.") is None      # defect-3 debris
    assert french_ordinal(None) is None


def test_french_and_font_are_separate_scales():
    # The whole point of having two functions: the scales share spellings but
    # not meanings, and neither is defined on the other's territory.
    # 9c exists in sport and nowhere on the Font scale.
    assert french_ordinal("9c") is not None and font_ordinal("9c") is None
    # ...and their ordinals are not comparable: same spelling, different index.
    assert french_ordinal("8a") != font_ordinal("8A")


def test_is_french_grade():
    assert is_french_grade("8c+")
    assert is_french_grade("9b/9b+")
    assert not is_french_grade("E4")
    assert not is_french_grade(None)


def test_french_to_yds():
    assert french_to_yds("9a") == "5.14d"
    assert french_to_yds("9c") == "5.15d"
    assert french_to_yds("E4") is None


# ── Font boulder scale (the control group still sorts on it) ─────────────────


def test_font_scale_orders_numerically_not_lexically():
    assert font_ordinal("4") < font_ordinal("7A") < font_ordinal("8A") < font_ordinal("9A")


def test_font_scale_is_strictly_increasing():
    ordinals = [font_ordinal(g) for g in FONT_SCALE]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)


def test_font_to_v():
    assert font_to_v("8B") == 13
    assert font_to_v("9A") == 17
    assert font_to_v("4") is None  # below where the scales align


# ── Ascent dates ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4th Jun 2017", pd.Timestamp(2017, 6, 4)),
        ("14th Jun 1990", pd.Timestamp(1990, 6, 14)),
        ("Jul 1998", pd.Timestamp(1998, 7, 1)),
        ("1990", pd.Timestamp(1990, 1, 1)),
        ("Before Jan 1995", pd.Timestamp(1995, 1, 1)),
        ("Before 8th Aug 2026", pd.Timestamp(2026, 8, 8)),
        ("1st January 2020", pd.Timestamp(2020, 1, 1)),
    ],
)
def test_parse_ascent_date(raw, expected):
    assert parse_ascent_date(raw) == expected


def test_parse_ascent_date_returns_none_for_unparseable():
    # None rather than Timestamp.max, so callers choose how unknowns sort.
    assert parse_ascent_date("sometime in the eighties") is None
    assert parse_ascent_date(None) is None
    assert parse_ascent_date("") is None
