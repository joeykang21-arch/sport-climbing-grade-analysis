"""Regression tests for the three header defects in the raw scrape.

The current scraper heads defects 1 and 2 off at the source, and the fresh
snapshot confirms it (see HANDOFF.md). The repairs are pinned here anyway:
they are what keeps ``data/raw/archive/`` — collected by the older scraper,
which did produce all three — readable with the same code.
"""

import pandas as pd
import pytest

from sportgradehistory.clean import (
    clean_detail_frame,
    is_known_type,
    split_type_and_location,
    strip_nav_suffix,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # The original spelling, as found throughout data/raw/archive/.
        ("Malham Cove More Change Log Threads", "Malham Cove"),
        ("Raven Tor More 1 Change Log Threads 1", "Raven Tor"),
        ("Branson More 2 Change Log Threads 2", "Branson"),
        ("Bas Cuvier More 3 Change Log Threads 3", "Bas Cuvier"),
        ("Boulder problem More Change Log Threads", "Boulder problem"),
        # The spellings the site produces since the Notes Log tab was added.
        ("Malham Cove More Change Log Notes Log Threads", "Malham Cove"),
        ("Malham Cove More Notes Log", "Malham Cove"),
        ("Ceuse More Change Log Notes Log Threads 2", "Ceuse"),
        ("Fontainebleau", "Fontainebleau"),
        ("More Change Log Threads", None),
        (None, None),
        (float("nan"), None),
        (pd.NA, None),
    ],
)
def test_strip_nav_suffix(raw, expected):
    assert strip_nav_suffix(raw) == expected


def test_strip_nav_suffix_keeps_locations_containing_more():
    # "More" is a real word in crag and route names and must not trigger the
    # strip: the raw scrape has "No More Greener Grasses", "Forever More SDS".
    assert strip_nav_suffix("Moore Nook More Change Log Threads") == "Moore Nook"
    assert strip_nav_suffix("No More Greener Grasses") == "No More Greener Grasses"
    assert strip_nav_suffix("Forever More SDS") == "Forever More SDS"
    # A location legitimately ending in the bare word survives too: the suffix
    # is only stripped when "More" is followed by at least one tab label.
    assert strip_nav_suffix("Point of No Return More") == "Point of No Return More"


@pytest.mark.parametrize(
    "climb_type, expected_type, expected_location",
    [
        ("Sport route in Chee Dale", "Sport route", "Chee Dale"),
        ("Trad climb on Dinas Cromlech", "Trad climb", "Dinas Cromlech"),
        ("Boulder problem at Fontainebleau", "Boulder problem", "Fontainebleau"),
        ("Multi-pitch on the Tre Cime", "Multi-pitch", "the Tre Cime"),
        ("(approx) Boulder problem in Brione", "(approx) Boulder problem", "Brione"),
        ("Boulder problem (indoor)", "Boulder problem (indoor)", None),
        ("Deep water solo", "Deep water solo", None),
    ],
)
def test_split_type_and_location(climb_type, expected_type, expected_location):
    assert split_type_and_location(climb_type, None) == (expected_type, expected_location)


def test_split_prefers_the_scraped_location():
    # A location the scraper did capture is authoritative and is not overwritten
    # by the fragment fused into the type.
    assert split_type_and_location("Sport route in Chee Dale", "Two Tier Buttress") == (
        "Sport route",
        "Two Tier Buttress",
    )


def test_split_leaves_unrecognised_types_alone():
    # Better to surface an unexpected value than to guess at a split.
    assert split_type_and_location("Snow gully in Scotland", None) == (
        "Snow gully in Scotland",
        None,
    )


def test_is_known_type():
    assert is_known_type("Boulder problem")
    assert is_known_type("Trad climb on Millstone Edge")
    assert not is_known_type("Everest")
    assert not is_known_type(None)


def _frame(rows):
    columns = [
        "climb_id", "climb_url", "climb_name", "grade", "climb_type", "location",
        "num_ascents", "first_climber", "first_style", "first_ascent_date",
        "first_suggested_grade",
    ]
    return pd.DataFrame(rows, columns=columns)


def test_clean_detail_frame_fixes_all_three_defects():
    raw = _frame(
        [
            # Defect 1: nav text on the location (archive spelling).
            (4, "u/4", "Rainman", "9b", "Sport route",
             "Malham Cove More Change Log Threads", 3, "Steve McClure",
             "Lead | worked", "4th Jun 2017", "9b"),
            # Defect 2: location fused into the type, location left empty.
            (73, "u/73", "Kaabah", "8c", "Sport route in Chee Dale More Change Log Threads",
             None, 5, "Ben Moon", None, "1990", None),
            # Defect 3: no grade in the heading, so the columns are shifted.
            # Still live in the current snapshot (climb 2627 among others).
            (2627, "u/2627", "Southeast Ridge", "Mt.", "Everest More Change Log Threads",
             None, 1, "Tenzing Norgay", None, "29th May 1953", None),
        ]
    )

    clean = clean_detail_frame(raw)

    assert len(clean) == len(raw)  # cleaning never drops or adds rows

    assert clean.loc[0, "location"] == "Malham Cove"
    assert clean.loc[0, "climb_type"] == "Sport route"

    assert clean.loc[1, "climb_type"] == "Sport route"
    assert clean.loc[1, "location"] == "Chee Dale"

    assert pd.isna(clean.loc[2, "grade"])
    assert pd.isna(clean.loc[2, "climb_type"])
    assert clean.loc[2, "location"] == "Mt. Everest"


def test_clean_detail_frame_leaves_no_nav_text_anywhere():
    raw = _frame(
        [
            (1, "u/1", "A", "8A", "Boulder problem",
             "Bas Cuvier More Change Log Threads", 2, "Someone", None, "1990", "8A"),
            (2, "u/2", "B", "7C", "Boulder problem in Brione More 2 Change Log Threads 2",
             None, 1, "Someone", None, "1991", None),
            (3, "u/3", "C", "9a", "Sport route",
             "Ceuse More Change Log Notes Log Threads", 4, "Someone", None, "1992", None),
        ]
    )

    clean = clean_detail_frame(raw)

    cells = clean.astype(str).to_numpy().ravel().tolist()
    assert not any("Change Log" in str(cell) for cell in cells)
    assert not any("Notes Log" in str(cell) for cell in cells)


def test_clean_detail_frame_preposition_free_fused_location_is_the_known_cost():
    # Climb 5873 in the current snapshot: the heading has no "at"/"in"/"on", so
    # the location fuses into the type with nothing to split on. The defect-3
    # repair cannot tell this from a column shift and moves everything into
    # `location`. One row, documented in HANDOFF.md, pinned here so the
    # behaviour is at least deliberate.
    raw = _frame(
        [
            (5873, "u/5873", "Substance of Everything", "8B",
             "Boulder problem The Frontline", None, 3, "Someone", None, "2023", None),
        ]
    )

    clean = clean_detail_frame(raw)

    assert pd.isna(clean.loc[0, "grade"])
    assert pd.isna(clean.loc[0, "climb_type"])
    assert clean.loc[0, "location"] == "8B Boulder problem The Frontline"
