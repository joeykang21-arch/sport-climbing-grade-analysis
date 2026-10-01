"""Generate ``visualizations/boulder-regrades-by-grade.html``.

The boulder answer to the sport pages in :mod:`build_regrade_pages`: over the
Font-scale grade eras, which problems first climbed inside each one later
settled above (upgrades) or below (downgrades) the first ascentionist's own
suggestion.

It carries **one** chart — the diverging "both directions, era by era" overview,
drawn by :func:`build_regrade_pages.overview_svg` so the boulder bars and the
sport bars are literally the same mark at the same scale. The per-era route
lists and timelines the sport pages carry are deliberately absent: this page is
the comparison, not the catalogue.

Why the boulder side is worth drawing at all: the suggested-grade field is much
better populated here than on the sport side — 214 problems disagree with their
FA suggestion against 85 routes — so the same question gets two and a half times
the evidence, and the up/down balance comes out the other way round.

Eras are read off the Font ceiling from 8A up, the boulder analogue of the sport
analysis starting at 8a+. Eight grades have an ascent in this snapshot, 8A to
9A+, and the last of them is still open; 9B is on the Font scale but nothing in
the data holds it, so no ninth era is drawn.

Self-contained HTML: inline CSS, inline SVG, no JavaScript, no build step.

Run as::

    python -m sportgradehistory.build_boulder_regrade_pages
"""

from __future__ import annotations

import pandas as pd

from . import config
from .build_regrade_pages import (
    DOWNGRADES, EXTRA_CSS, UPGRADES, Direction, frontier_split, load_regrades,
    overview_svg,
)
from .build_runway_pages import CSS, SCRAPE_DATE, VIZ_DIR, Era, esc
from .grades import FONT_SCALE, font_ordinal

OUT_NAME = "boulder-regrades-by-grade.html"

# Where the boulder era ladder starts. 8A is one notch under 8A+, and the sport
# analysis starts one notch under its own first milestone for the same reason:
# the era below the frontier is the context the frontier is read against.
ERA_START = "8A"

# Problems whose suggested-grade field disagrees with the consensus for a
# reason other than a regrade, dropped from the selection by climb id. Each
# entry names what the field really holds, so the exclusion can be retired if a
# later scrape corrects it.
NOT_REGRADES: dict[int, str] = {
    # Kaizen, Torrelodones. The FA's "9a" is a route grade, not Font 9A;
    # ``font_ordinal`` case-folds it into a 9A suggestion and a phantom
    # two-grade downgrade to 8C.
    4170: "suggestion given on the route scale (9a), not Font",
    # Blackflip SDS, Djan-Tugan. The "8C+/9A" suggestion was later raised to
    # 9A by the first ascentionist, so the consensus agrees with the
    # FA's own final grade and there is no upgrade by anyone else.
    2532: "retroactively upgraded by the first ascentionist",
}


def load_boulders() -> pd.DataFrame:
    """``boulders.csv``, with the site's duplicate entries dropped.

    The same rule ``load_sport`` and ``load_regrades`` apply — an identical
    (name, location, FA date) triple is one problem filed twice under two climb
    ids, so the lower id is kept. It matters more here than on the sport side:
    16 of the 3,098 boulder rows are duplicates, one of them a regrade.
    """
    df = pd.read_csv(config.BOULDERS_CSV, encoding="utf-8")
    df["first_ascent"] = pd.to_datetime(df["first_ascent"])
    return df.sort_values("climb_id", kind="stable").drop_duplicates(
        subset=["climb_name", "location", "first_ascent_date"], keep="first")


def select_regrades(boulders: pd.DataFrame) -> pd.DataFrame:
    """Problems whose consensus Font grade differs from the FA suggestion.

    ``build_datasets.select_regraded`` does this for sport and writes
    ``regraded_routes.csv``; there is no boulder equivalent on disk, so the
    same three columns — ``suggested_clean``, ``suggested_order``,
    ``direction`` — are derived here against ``font_ordinal`` instead of
    ``french_ordinal``. Thirteen suggestions do not parse as Font grades (they
    are V grades or free text) and drop out with them, as do the problems in
    :data:`NOT_REGRADES`.
    """
    suggested_order = boulders["first_suggested_grade"].map(font_ordinal)
    changed = (
        ~boulders["climb_id"].isin(NOT_REGRADES)
        & suggested_order.notna()
        & boulders["grade_order"].notna()
        & (suggested_order != boulders["grade_order"])
    )

    out = boulders[changed].copy()
    out["suggested_order"] = suggested_order[changed]
    out["suggested_clean"] = out["suggested_order"].map(
        lambda o: FONT_SCALE[int(o)])
    out["direction"] = (
        (out["grade_order"] - out["suggested_order"])
        .gt(0).map({True: "upgrade", False: "downgrade"}))
    return out.sort_values("first_ascent", kind="stable").reset_index(drop=True)


def breakthroughs(boulders: pd.DataFrame, start: str = ERA_START) -> pd.DataFrame:
    """When the boulder ceiling first reached each grade, from ``start`` up.

    The Font-scale twin of :func:`milestones.breakthrough_table`, kept separate
    rather than folded into it: that function is wired to the French scale and
    to sport's curated tie-breaks, disputed claims and FA supplements, none of
    which has a boulder counterpart in this repo. What it does share is the
    monotonic pass — a grade's breakthrough can never postdate a harder grade's
    — so the era windows can never overlap or run backwards.
    """
    cutoff = font_ordinal(start)
    frame = boulders[
        boulders["grade_order"].notna()
        & (boulders["grade_order"] >= cutoff)
        & boulders["first_ascent"].notna()
    ]

    rows = []
    for ordinal in sorted(frame["grade_order"].unique()):
        first = frame[frame["grade_order"] == ordinal].sort_values(
            ["first_ascent", "climb_id"], kind="stable").iloc[0]
        rows.append({
            "grade": FONT_SCALE[int(ordinal)],
            "grade_order": int(ordinal),
            "problem": first["climb_name"],
            "climber": first["first_climber"],
            "first_ascent": first["first_ascent"],
        })

    out = pd.DataFrame(rows)
    for i in range(len(out) - 2, -1, -1):
        later = out.iloc[i + 1]
        if later["first_ascent"] < out.iloc[i]["first_ascent"]:
            for col in ("problem", "climber", "first_ascent"):
                out.iloc[i, out.columns.get_loc(col)] = later[col]
    return out


def collect_eras(boulders: pd.DataFrame, regraded: pd.DataFrame,
                 direction: Direction) -> list[Era]:
    """One Era per boulder grade, each holding its own regrades.

    A problem is placed by *when it was climbed*, not by what grade it ended up
    at — the same rule the sport pages use, and the reason an 8C cut back to 8B+
    counts against the era that was running at its FA rather than against 8B+.
    """
    table = breakthroughs(boulders)
    moves = regraded[regraded["direction"] == direction.key]
    eras: list[Era] = []

    for i, row in table.iterrows():
        is_last = i == len(table) - 1
        nxt = None if is_last else table.iloc[i + 1]
        start = row["first_ascent"]
        end = SCRAPE_DATE if is_last else nxt["first_ascent"]

        in_era = moves[
            moves["first_ascent"].notna()
            & (moves["first_ascent"] >= start)
            & (moves["first_ascent"] < end)
        ].sort_values("first_ascent")

        eras.append(Era(
            grade=row["grade"],
            next_grade=None if is_last else nxt["grade"],
            start=start,
            end=end,
            breakthrough=None if is_last else nxt["problem"],
            routes=in_era,
            open_era=is_last,
        ))
    return eras


def chart_totals() -> tuple[int, int]:
    """The up/down counts the page actually draws, for the index to quote.

    Not the same as the number of regrades found: a problem with no usable FA
    date, or one climbed before the 8A ceiling existed, has no era to sit in and
    so never reaches the chart. The index has to quote what a reader will
    count on the page, not what the filter found on the way there.
    """
    boulders = load_boulders()
    regraded = select_regrades(boulders)
    up, down = (
        sum(len(e.routes) for e in collect_eras(boulders, regraded, d))
        for d in (UPGRADES, DOWNGRADES)
    )
    return up, down


def span_phrase(era: Era) -> str:
    """An era's length in words, with a zero-length one said out loud.

    Meathook (8A) and Trice (8A+) are both dated to 1975 and nothing finer, so
    the parser anchors both to 1 January and the 8A era comes out with no span
    at all. That is an artifact of the record's precision, not a claim that the
    ceiling rose twice in a day, so the band is kept and labelled rather than
    quietly dropped.
    """
    if era.years < 1 / 365.25:
        return "no measurable span"
    if era.years < 1:
        return f"~{max(round(era.years * 12), 1)} mo"
    return f"~{era.years:.1f} yrs"


def page(up_eras: list[Era], down_eras: list[Era], found: int,
         sport_found: int) -> str:
    ups = [len(e.routes) for e in up_eras]
    downs = [len(e.routes) for e in down_eras]
    fr_up = [frontier_split(e, font_ordinal)[0] for e in up_eras]
    fr_down = [frontier_split(e, font_ordinal)[0] for e in down_eras]
    total, frontier = sum(ups) + sum(downs), sum(fr_up) + sum(fr_down)
    peak = down_eras[fr_down.index(max(fr_down))]

    # the zero-span era cannot be compared on length, so it sits out the
    # shortest/longest sentence rather than winning it on an artifact
    by_span = sorted((e for e in up_eras if e.years >= 1 / 365.25),
                     key=lambda e: e.years)
    empty = [u.grade for u, d in zip(up_eras, down_eras)
             if not len(u.routes) and not len(d.routes)]
    empty_note = (
        f" The {esc(empty[0])} and {esc(empty[1])} bands are empty because the "
        f"suggested-grade field is effectively unpopulated that early, not "
        f"because nothing moved."
        if len(empty) >= 2 else "")

    ladder = " &rarr; ".join(esc(e.grade) for e in up_eras)
    by_era = ", ".join(f"{esc(e.grade)} {u}&uarr;/{d}&darr;"
                       for e, u, d in zip(up_eras, ups, downs))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boulder upgrades and downgrades by grade era</title>
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body><main>
<nav class="top"><a href="index.html">&larr; all timelines</a> &middot;
<a href="upgrades-by-grade.html">sport upgrades</a> &middot;
<a href="downgrades-by-grade.html">sport downgrades</a></nav>
<h1>Which boulder problems moved while each grade held the ceiling</h1>
<p>The sport question, asked of the boulder control group. Each era runs from
the first problem at a Font grade to the first problem at the next
({ladder}), and a problem is counted in the era it was <em>climbed</em> in, not
the one its final grade belongs to. Its move is the first ascentionist&rsquo;s
suggestion read against today&rsquo;s consensus: {found} problems settled away
from what their own first ascentionist said, and {total} of them fall inside an
era window &mdash; {sum(ups)} upward and {sum(downs)} downward. The
{found - total} left out have no usable first-ascent date, or predate the 8A
ceiling, so there is no era to put them in.</p>
<p>The boulder record is the better populated of the two. The site carries an FA
suggestion for enough problems to put {total} moves on this chart against
{sport_found} on the sport pages &mdash; and the balance runs the other way,
downgrades clearly ahead of upgrades where sport leans up. Both are floors
rather than censuses: a problem with no recorded suggestion cannot appear, and
that is a fact about the record rather than about the climbing.</p>
<section id="overview">
<div class="head"><h2>Both directions, era by era</h2>
<span class="sub">{sum(ups)} up and {sum(downs)} down across the
{len(up_eras)} eras, {frontier} of them at the frontier</span></div>
{overview_svg(up_eras, down_eras, font_ordinal, link=False)}
<p class="note">The lighter part of each bar is the moves that touched the
era&rsquo;s own top grade &mdash; an upgrade that arrived at the ceiling, or a
downgrade claimed at or above it and then cut back. Only {frontier} of the
{total} moves qualify, {max(fr_down)} of them downgrades in the
{esc(peak.grade)} era alone; nearly all boulder regrading happens in the
backlog below the frontier, which is the shape the sport pages show too.\
{empty_note}</p>
<p class="note">Counts, not rates: the dated eras run from
{span_phrase(by_span[0]).lstrip("~")} ({esc(by_span[0].grade)}) to
{span_phrase(by_span[-1]).lstrip("~")} ({esc(by_span[-1].grade)}), so a tall bar
can mean a long era as much as a busy one. Both arms share one scale, and the
lighter parts sit on the gutter so they can be compared across eras. Hover a
band for the split.</p>
<p class="note">{esc(up_eras[0].grade)} has {span_phrase(up_eras[0])}: Meathook
({esc(up_eras[0].grade)}) and Trice ({esc(up_eras[1].grade)}) are both recorded
as 1975 and nothing finer, so both anchor to 1&nbsp;January and the era between
them closes the day it opens. The band is kept rather than dropped, because the
missing span is missing from the record, not from the history.</p>
</section>
<footer>Moves by era: {by_era} &middot;
Data: <a href="https://climbing-history.org">climbing-history.org</a>,
scraped 2026-09-09 &middot; consensus Font grade against the recorded
suggestion &middot; problems from
<code>data/processed/boulders.csv</code> &middot; part of
<a href="https://github.com/joeykang21-arch">sport-grade-history</a></footer>
</main></body>
</html>"""


def build() -> None:
    boulders = load_boulders()
    regraded = select_regrades(boulders)
    eras = {d.key: collect_eras(boulders, regraded, d)
            for d in (UPGRADES, DOWNGRADES)}

    # The sport figure the page compares itself against, counted rather than
    # written down, so the comparison cannot drift when the scrape is refreshed.
    sport_found = len(load_regrades())

    out = VIZ_DIR / OUT_NAME
    out.write_text(
        page(eras[UPGRADES.key], eras[DOWNGRADES.key], len(regraded),
             sport_found),
        encoding="utf-8")
    print(f"wrote {out}")

    placed = 0
    for u, d in zip(eras[UPGRADES.key], eras[DOWNGRADES.key]):
        placed += len(u.routes) + len(d.routes)
        print(f"  {u.grade:>4}: {len(u.routes):>3} up, {len(d.routes):>3} down "
              f"({frontier_split(u, font_ordinal)[0]}/"
              f"{frontier_split(d, font_ordinal)[0]} at the frontier)")
    print(f"  {placed} of {len(regraded)} regrades fall inside an era window")


def main() -> None:
    build()


if __name__ == "__main__":
    main()
