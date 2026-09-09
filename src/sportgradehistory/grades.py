"""Grade and ascent-date parsing helpers.

climbing-history.org records grades as free text. Two things make them awkward
to work with:

* Consensus-uncertain grades are written as a slash pair (``"9a/9a+"``) or with
  a qualifier (``"8c (soft)"``).
* Neither climbing scale sorts lexicographically: plain string ordering puts
  ``"7a"`` after ``"8c"`` and ``"10"`` before ``"3"``.

:func:`clean_grade` handles the first. The second needs one function per scale,
because **the scales are different and must not be shared**:

* :func:`font_ordinal` — the Font bouldering scale (``6A``, ``8B+``, ``9A``).
* :func:`french_ordinal` — the French sport scale (``6a``, ``8b+``, ``9c``).

They are separate lists with separate index tables. Font has no ``9c`` and
French has no ``9A``; the sub-6a ends diverge completely (Font counts ``4``,
``4+``, ``5``, ``5+`` where French uses ``5a``, ``5b``, ``5c``); and the two
disagree on difficulty at every shared spelling — Font ``8A`` is nowhere near
French ``8a``. Case is how the raw data distinguishes them, but callers pick a
scale by choosing the function rather than by relying on case surviving.
"""

from __future__ import annotations

import re

import pandas as pd

# The Font bouldering scale in ascending order. Used to sort boulder grades.
FONT_SCALE = [
    "1", "2", "3", "4", "4+",
    "5", "5+",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
    "9A", "9A+", "9B",
]

_FONT_INDEX = {grade.upper(): i for i, grade in enumerate(FONT_SCALE)}

# The French sport scale in ascending order.
#
# Below 6a the scale subdivides as 4a/4b/4c and 5a/5b/5c. The bare "4"/"5"/"5+"
# spellings are also recorded on the site for older or coarsely graded routes,
# so both forms are kept and the bare number is placed just below the "a" of the
# same number. The top of the scale stops at 9c (Silence, 2017), the hardest
# grade currently claimed -- it is extended when the data needs it, not before.
FRENCH_SCALE = [
    "1", "2", "3",
    "4", "4a", "4b", "4c", "4+",
    "5", "5a", "5b", "5c", "5+",
    "6a", "6a+", "6b", "6b+", "6c", "6c+",
    "7a", "7a+", "7b", "7b+", "7c", "7c+",
    "8a", "8a+", "8b", "8b+", "8c", "8c+",
    "9a", "9a+", "9b", "9b+", "9c",
]

_FRENCH_INDEX = {grade.lower(): i for i, grade in enumerate(FRENCH_SCALE)}

# Font grade -> V grade. The mapping is the widely used approximation; boundary
# grades below 6C are deliberately absent because the scales do not line up.
FONT_TO_V = {
    "6C": 5, "6C+": 6,
    "7A": 6, "7A+": 7, "7B": 8, "7B+": 8, "7C": 9, "7C+": 10,
    "8A": 11, "8A+": 12, "8B": 13, "8B+": 14, "8C": 15, "8C+": 16,
    "9A": 17, "9A+": 18, "9B": 19,
}

# French sport grade -> YDS. The usual conversion, offered for readers who think
# in 5.x; the datasets sort on french_ordinal, never on this.
FRENCH_TO_YDS = {
    "6a": "5.10a", "6a+": "5.10b", "6b": "5.10c", "6b+": "5.10d",
    "6c": "5.11a", "6c+": "5.11b",
    "7a": "5.11d", "7a+": "5.12a", "7b": "5.12b", "7b+": "5.12c",
    "7c": "5.12d", "7c+": "5.13a",
    "8a": "5.13b", "8a+": "5.13c", "8b": "5.13d", "8b+": "5.14a",
    "8c": "5.14b", "8c+": "5.14c",
    "9a": "5.14d", "9a+": "5.15a", "9b": "5.15b", "9b+": "5.15c", "9c": "5.15d",
}

_ORDINAL_SUFFIX = re.compile(r"(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
_BEFORE_PREFIX = re.compile(r"^before\s+", re.IGNORECASE)
_APPROX_PREFIX = re.compile(r"^\(approx\)\s*", re.IGNORECASE)
# Consensus qualifiers the site appends: "8b (soft)", "8c (hard)".
_QUALIFIER_SUFFIX = re.compile(r"\s*\((?:soft|hard)\)\s*$", re.IGNORECASE)

_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%b %Y", "%B %Y", "%Y")


def clean_grade(grade: object) -> str | None:
    """Normalise a raw grade string to a single scale point.

    Takes the lower half of a slash pair (``"9a/9a+"`` -> ``"9a"``,
    ``"8C+/9b"`` -> ``"8C+"``) and drops the ``(approx)`` prefix and the
    ``(soft)`` / ``(hard)`` consensus qualifier. Case is left alone, because it
    is the only thing distinguishing a Font grade from a French one in the raw
    data. Returns ``None`` for missing or empty input.
    """
    if grade is None or (isinstance(grade, float) and pd.isna(grade)):
        return None

    text = _APPROX_PREFIX.sub("", str(grade)).split("/")[0]
    text = _QUALIFIER_SUFFIX.sub("", text).strip()
    return text or None


def font_ordinal(grade: object) -> int | None:
    """Return the position of ``grade`` on the **Font boulder** scale, or ``None``.

    Sorting on this rather than on the raw string is what keeps ``7A`` below
    ``8A`` and ``4`` below ``10``. Off-scale grades (French, UK trad, YDS, aid)
    return ``None`` so they can be spotted rather than silently mis-sorted.
    """
    cleaned = clean_grade(grade)
    if cleaned is None:
        return None
    return _FONT_INDEX.get(cleaned.upper())


def french_ordinal(grade: object) -> int | None:
    """Return the position of ``grade`` on the **French sport** scale, or ``None``.

    The sport-side counterpart of :func:`font_ordinal`, and deliberately not
    built on it: the two scales share spellings but not meanings, so a grade is
    looked up in ``FRENCH_SCALE`` only. ``french_ordinal("9c")`` is defined,
    ``font_ordinal("9c")`` is ``None``, and neither ordinal is comparable with
    the other's.

    Lookup is case-folded, so a stray upper-case ``"8A"`` in a sport row still
    resolves. That is a convenience for dirty data, not a licence to mix scales:
    a row's scale is decided by which function the caller chose.
    """
    cleaned = clean_grade(grade)
    if cleaned is None:
        return None
    return _FRENCH_INDEX.get(cleaned.lower())


def font_to_v(grade: object) -> int | None:
    """Convert a Font bouldering grade to its approximate V grade."""
    cleaned = clean_grade(grade)
    if cleaned is None:
        return None
    return FONT_TO_V.get(cleaned.upper())


def french_to_yds(grade: object) -> str | None:
    """Convert a French sport grade to its approximate YDS grade."""
    cleaned = clean_grade(grade)
    if cleaned is None:
        return None
    return FRENCH_TO_YDS.get(cleaned.lower())


def is_french_grade(grade: object) -> bool:
    """Whether ``grade`` is a point on the French sport scale.

    This is what separates sport routes from the trad and alpine climbs that
    share their ``climb_type`` on the site: an ``E4`` or a ``5.12a`` is not on
    the scale and answers ``False``.
    """
    return french_ordinal(grade) is not None


def parse_ascent_date(value: object) -> pd.Timestamp | None:
    """Parse an ascent date such as ``"4th Jun 2017"``, ``"Jul 1998"`` or ``"1990"``.

    A leading ``"Before "`` is dropped and the remaining date is used as an
    upper bound. Year-only and month-only values are anchored to the first day
    of the period. Returns ``None`` when nothing parses, so callers can decide
    how to order unknown dates rather than having that choice made for them.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, pd.Timestamp):
        return value

    text = str(value).strip()
    if not text:
        return None

    text = _BEFORE_PREFIX.sub("", text)
    text = _ORDINAL_SUFFIX.sub(r"\1", text).strip()

    for fmt in _DATE_FORMATS:
        try:
            return pd.to_datetime(text, format=fmt)
        except (ValueError, TypeError):
            continue
    return None


def add_grade_columns(
    df: pd.DataFrame, grade_column: str = "grade", ordinal=font_ordinal
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``grade_clean`` and ``grade_order`` added.

    ``ordinal`` selects the scale: pass :func:`font_ordinal` for boulders and
    :func:`french_ordinal` for sport routes. There is no autodetection, because
    guessing a scale from a string that both scales spell the same way is how
    grades end up silently mis-sorted.
    """
    out = df.copy()
    out["grade_clean"] = out[grade_column].map(clean_grade)
    out["grade_order"] = out[grade_column].map(ordinal)
    return out
