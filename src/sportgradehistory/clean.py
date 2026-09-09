"""Repair the header fields produced by the raw climb-page scrape.

The climb page renders its navigation dropdown inside the ``<h1>``, so reading
the heading with ``get_text(" ", strip=True)`` picks the tab labels up too.
Three defects follow from that, and each is fixed here so an already-collected
raw file can be repaired without re-scraping:

1. **Trailing navigation text.** The row ends in some form of
   ``"More Change Log Notes Log Threads"`` -- the tab labels, occasionally
   carrying their badge counts. It lands on ``location``, or on ``climb_type``
   when the climb has no location.

2. **Location fused into the type.** The heading is split on ``" at "`` only,
   but the site also writes ``" in "`` and ``" on "``, which leaves the crag
   inside ``climb_type`` and ``location`` empty.

3. **Column shift on ungraded routes.** A handful of alpine routes carry no
   grade, so the heading is just ``"Name | Mt. Everest"``. Positional parsing
   reads ``grade == "Mt."`` and ``climb_type == "Everest"``.

:mod:`sportgradehistory.scrape_details` heads defects 1 and 2 off at the source,
so a fresh scrape should not contain them. The repairs are kept anyway: they are
what makes ``data/raw/archive/`` -- collected by the older scraper, which did
produce them -- readable with the same code. See HANDOFF.md for which defects
the current snapshot actually contains.
"""

from __future__ import annotations

import re

import pandas as pd

# Tab labels that can appear appended to the <h1> text, each optionally carrying
# a badge count ("Threads 2").
_NAV_TOKEN = r"(?:More|Change\s+Log|Notes\s+Log|Threads|Ascents|Info)(?:\s+\d+)?"

# The run always opens with the "More" dropdown toggle and is followed by at
# least one tab label, so requiring both keeps a crag legitimately ending in the
# word "More" -- or named "Threads" -- from being truncated.
#
# Matches every form the site has used:
#     "More Change Log Threads"              (original)
#     "More 2 Change Log Threads 2"          (with badge counts)
#     "More Change Log Notes Log Threads"    (after the Notes Log tab was added)
#     "More Notes Log"
NAV_SUFFIX = re.compile(
    rf"\s*\bMore\b(?:\s+\d+)?(?:\s+{_NAV_TOKEN})+\s*$",
    re.IGNORECASE,
)

# The climb types the site uses, longest first so "Boulder problem (indoor)"
# wins over "Boulder problem". An optional "(approx)" marks an estimated grade.
CLIMB_TYPES = [
    "Boulder problem (indoor)",
    "Boulder problem",
    "Deep water solo",
    "Sport route",
    "Multi-pitch",
    "Trad climb",
    "Aid Climb",
    "Traverse",
    "Alpine",
]

_TYPE_ALTERNATION = "|".join(re.escape(t) for t in CLIMB_TYPES)

# "Sport route in Chee Dale" / "Trad climb on Dinas Cromlech" / "... at Ceuse"
TYPE_WITH_LOCATION = re.compile(
    rf"^(?P<type>(?:\(approx\)\s*)?(?:{_TYPE_ALTERNATION}))"
    r"(?:\s+(?:in|on|at)\s+(?P<location>.+))?$",
    re.IGNORECASE,
)


def _is_missing(value: object) -> bool:
    """Whether ``value`` is any of the several nulls that reach these columns.

    Raw CSV reads give ``float('nan')``, nullable string columns give ``pd.NA``,
    and re-parsed frames give ``None``. ``pd.isna`` covers all three but returns
    an array for sequences, so scalars are checked explicitly.
    """
    return value is None or (pd.api.types.is_scalar(value) and pd.isna(value))


def strip_nav_suffix(value: object) -> str | None:
    """Remove a trailing run of navigation tab labels from ``value``."""
    if _is_missing(value):
        return None
    text = NAV_SUFFIX.sub("", str(value)).strip()
    return text or None


def split_type_and_location(
    climb_type: object, location: object
) -> tuple[str | None, str | None]:
    """Separate a fused ``"<type> in <location>"`` string into its two parts.

    An existing ``location`` is authoritative and never overwritten; the split
    only fills a location the scraper failed to capture. A ``climb_type`` that
    does not start with a known type is left untouched rather than guessed at,
    so unexpected values stay visible instead of being silently mangled.
    """
    climb_type = strip_nav_suffix(climb_type)
    location = strip_nav_suffix(location)

    if climb_type is None:
        return None, location

    match = TYPE_WITH_LOCATION.match(climb_type)
    if match is None:
        return climb_type, location

    parsed_type = match.group("type")
    parsed_location = match.group("location")

    return parsed_type, location or parsed_location


def is_known_type(value: object) -> bool:
    """Whether ``value`` starts with one of the site's climb types.

    This is what identifies defect 3: the grades themselves span five scales
    (Font, French, UK adjectival, aid, alpine) and are too varied to validate,
    but the type vocabulary is small and closed, so a ``climb_type`` outside it
    means the columns have shifted.
    """
    if _is_missing(value):
        return False
    return TYPE_WITH_LOCATION.match(str(value).strip()) is not None


def unknown_types(df: pd.DataFrame) -> pd.Series:
    """Count the ``climb_type`` values that :data:`CLIMB_TYPES` does not cover.

    Worth checking after every scrape. ``clean_detail_frame`` treats a graded
    row with an unrecognised type as a column shift, so a type the site has
    added since this list was written would be misread as defect 3 rather than
    reported. An empty result means the vocabulary is still complete.
    """
    types = df["climb_type"].dropna().astype("string")
    return types[~types.map(is_known_type)].value_counts()


def clean_detail_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the raw detail frame with all three header defects fixed.

    Adds no columns and drops no rows, so the result lines up one-to-one with
    the raw scrape and the two can be diffed directly.
    """
    out = df.copy()

    for column in ("climb_name", "grade", "climb_type", "location", "first_climber"):
        if column in out.columns:
            out[column] = out[column].map(strip_nav_suffix).astype("string")

    # Defect 3: the header carries no grade, so `grade` and `climb_type` hold a
    # shifted fragment of the location ("Mt." / "Everest"). A graded row whose
    # type is not one the site uses is the tell. Rejoin the fragments into the
    # location and clear the two columns that were never really populated.
    shifted = out["grade"].notna() & ~out["climb_type"].map(is_known_type)
    if shifted.any():
        rejoined = (
            out.loc[shifted, "grade"].fillna("")
            + " "
            + out.loc[shifted, "climb_type"].fillna("")
        ).str.strip()
        out.loc[shifted, "location"] = out.loc[shifted, "location"].fillna(rejoined)
        out.loc[shifted, "grade"] = pd.NA
        out.loc[shifted, "climb_type"] = pd.NA

    # Defect 2: unfuse "<type> in <location>" into its two columns.
    split = out.apply(
        lambda row: split_type_and_location(row["climb_type"], row["location"]),
        axis=1,
        result_type="expand",
    )
    out["climb_type"] = split[0].astype("string")
    out["location"] = split[1].astype("string")

    if "num_ascents" in out.columns:
        out["num_ascents"] = pd.to_numeric(
            out["num_ascents"], errors="coerce"
        ).astype("Int64")

    return out


def clean_index_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the climbs-index scrape.

    The listing table is not affected by the ``<h1>`` defects, so this only
    normalises whitespace and makes the ascent count numeric.
    """
    out = df.copy()

    for column in out.select_dtypes(include=["object", "string"]).columns:
        out[column] = out[column].astype("string").str.strip().replace("", pd.NA)

    if "ascents_recorded" in out.columns:
        out["ascents_recorded"] = pd.to_numeric(
            out["ascents_recorded"], errors="coerce"
        ).astype("Int64")

    return out
