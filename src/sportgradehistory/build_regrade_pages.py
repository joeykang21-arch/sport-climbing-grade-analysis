"""Generate ``visualizations/upgrades-by-grade.html`` and
``visualizations/downgrades-by-grade.html``.

The runway page (:mod:`build_runway_pages`) asks what was *established* while
each grade held the ceiling. These two ask what later *moved*: over the same
era windows, every route first climbed inside one whose consensus grade settled
above (upgrades) or below (downgrades) the first ascentionist's own suggestion.

Same page shape as the runway page, deliberately — one section per era, the
same three tiles, the same numbered list against a numbered timeline — so the
three read as one family. The one change is the mark: an up or down arrow in
place of the runway's dot, because here the direction is the whole point.

The routes come from ``regraded_routes.csv``, the same table behind the per-era
tables in ``visualizations/grade-changes/``; these pages give those tables a
date axis and a single spine running across all ten eras.

The source's suggested-grade field is sparse, so every count is a floor rather
than a census. Eras with nothing recorded are kept and said out loud rather
than dropped — three of them are empty on the upgrade page and five on the
downgrade page, and that is a fact about the record, not about the climbing.

Self-contained HTML: inline CSS, inline SVG, no JavaScript, no build step —
same convention as ``build_runway_pages.py``.

Run as::

    python -m sportgradehistory.build_regrade_pages
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config
from .build_runway_pages import (
    CSS, SCRAPE_DATE, VIZ_DIR, Era, esc, plural, span_label, stack_rows,
)
from .grades import FRENCH_SCALE, french_ordinal
from .milestones import breakthrough_table, load_sport

# Direction reads as polarity, so the two marks take a warm/cool pair rather
# than two steps of one hue: the dark-surface steps of the green and rust the
# light `grade-changes` tables already use for `.tag.up` / `.tag.down`. The
# pair clears the CVD gate on the page's own #0e0e0f surface (worst deutan
# ΔE 9.4, target ≥ 8), and each clears the accent orange of the breakthrough
# marker it shares a chart with (14.0 down, 10.7 up).
UP_INK = "#199e70"
DOWN_INK = "#d95926"

# The frontier part of each bar is called out with a lighter step of its own
# hue, not a faded one: fading toward this near-black surface drops a fill to
# 1.6:1 — under the 3:1 a mark needs — and the faded part is most of the data.
# A lightness step also survives colour-blindness by construction (within the
# up arm ΔE 16.0, the down arm 17.0; across the gutter the two bases sit at
# 9.4). The two *light* steps measure only 5.5 against each other, but they are
# never a discrimination task: one is always above the gutter and one always
# below, each sitting on its own base hue, and each carries its count in text.
# Both light steps sit above the dark lightness band on purpose, as the page's
# accent already does — they are highlights, not another series.
UP_FRONTIER_INK = "#4fd3a4"
DOWN_FRONTIER_INK = "#f5a487"

# The longest either arm of the overview chart may draw, in pixels. It caps the
# bar length rather than the canvas: the two arms are stacked, so an uncapped
# scale turns a busy dataset into a chart taller than it is wide.
ARM_MAX = 200.0

EXTRA_CSS = """
:root { --up: #199e70; --down: #d95926; }
ol.routes .move { color: var(--ink); font-size: .85rem;
                  font-variant-numeric: tabular-nums; }
ol.routes .move b { font-size: .95rem; }
.up .move b { color: var(--up); }
.down .move b { color: var(--down); }
.empty { color: var(--dim); font-size: .9rem; margin: 1.1rem 0 .3rem;
         padding: .8rem .9rem; background: var(--panel);
         border: 1px solid var(--rule); border-radius: 6px; }

#overview { padding-top: 1.4rem; }
#overview .chart svg { min-width: 820px; }
.band .hit { fill: transparent; }
.band:hover .hit { fill: #f2f0ec; fill-opacity: .05; }
a:focus-visible .hit { fill: #f2f0ec; fill-opacity: .08; }
"""


@dataclass(frozen=True)
class Direction:
    """Everything that differs between the two pages, in one place."""

    key: str                 # the value in regraded_routes.direction
    ink: str                 # the arrow colour
    up: bool                 # which way the arrow points
    glyph: str               # the arrow in running text
    verb: str                # "moved up" / "moved down"
    comparative: str         # "harder" / "easier" than the suggestion
    filename: str
    title: str
    heading: str

    @property
    def noun(self) -> str:
        return f"{self.key}s"


UPGRADES = Direction(
    key="upgrade", ink=UP_INK, up=True, glyph="&uarr;", verb="moved up",
    comparative="harder", filename="upgrades-by-grade.html",
    title="Upgrades within each grade era",
    heading="Which routes moved up while each grade held the ceiling",
)
DOWNGRADES = Direction(
    key="downgrade", ink=DOWN_INK, up=False, glyph="&darr;",
    verb="moved down", comparative="easier", filename="downgrades-by-grade.html",
    title="Downgrades within each grade era",
    heading="Which routes moved down while each grade held the ceiling",
)


def load_regrades() -> pd.DataFrame:
    """``regraded_routes.csv``, with the site's duplicate entries dropped.

    Same rule ``load_sport`` applies: an identical (name, location, FA date)
    triple is one physical route filed twice under two climb ids, so the lower
    id is kept. One pair qualifies — Priorato de Sion at Alquézar, ids 3956 and
    3958, both 8c+ to 9a on 24 Mar 2008 — which is why the 9a+ era shows 23
    upgrades here and 24 in ``grade-changes/9a-plus-era-upgrades.html``, which
    reads the file raw. The chart is the reason to care: undeduplicated, the
    same route draws two identical arrows on the same date.
    """
    df = pd.read_csv(config.REGRADED_ROUTES_CSV, encoding="utf-8")
    df["first_ascent"] = pd.to_datetime(df["first_ascent"])
    return df.sort_values("climb_id", kind="stable").drop_duplicates(
        subset=["climb_name", "location", "first_ascent_date"], keep="first")


def collect_eras(sport: pd.DataFrame, regraded: pd.DataFrame,
                 direction: Direction) -> list[Era]:
    """One Era per milestone grade, each holding its own regrades.

    The windows are the runway page's windows exactly — from the breakthrough
    that opened an era to the one that closed it — but the routes inside them
    are selected by *when they were climbed*, not by what grade they hold, so
    a 9a upgraded from 8c+ lands in the era that was running at its FA.
    """
    milestones = breakthrough_table(sport, "as_consensus")
    moves = regraded[regraded["direction"] == direction.key]
    eras: list[Era] = []

    for i, row in milestones.iterrows():
        is_last = i == len(milestones) - 1
        nxt = None if is_last else milestones.iloc[i + 1]
        start = row["first_ascent"]
        end = SCRAPE_DATE if is_last else nxt["first_ascent"]

        in_era = moves[
            moves["first_ascent"].notna()
            & (moves["first_ascent"] >= start)
            & (moves["first_ascent"] < end)
        ].sort_values("first_ascent")

        eras.append(Era(
            grade=FRENCH_SCALE[int(row["grade_order"])],
            next_grade=None if is_last else nxt["grade"],
            start=start,
            end=end,
            breakthrough=None if is_last else nxt["route"],
            routes=in_era,
            open_era=is_last,
        ))
    return eras


def arrow_points(cx: float, cy: float, up: bool, scale: float = 1.0) -> str:
    """A numbered arrow the size of the runway page's dot, tip-first.

    Head and shaft rather than a bare triangle: the shaft is wide enough to
    carry the route's number, which is what ties a mark to its list entry.
    ``scale`` shrinks it for the overview legend, so the swatch there is
    literally the same glyph as the mark it stands for.
    """
    half_h, head_w, shaft_w = 14.0 * scale, 13.5 * scale, 9.0 * scale
    nib = 1.0 * scale
    tip = cy - half_h if up else cy + half_h
    shoulder = cy - nib if up else cy + nib
    base = cy + half_h if up else cy - half_h
    pts = [
        (cx, tip),
        (cx + head_w, shoulder), (cx + shaft_w, shoulder),
        (cx + shaft_w, base), (cx - shaft_w, base),
        (cx - shaft_w, shoulder), (cx - head_w, shoulder),
    ]
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def number_baseline(cy: float, up: bool) -> float:
    """Centre the number in the shaft, which sits below the head or above it."""
    shoulder = cy - 1.0 if up else cy + 1.0
    base = cy + 14.0 if up else cy - 14.0
    return (shoulder + base) / 2 + 4.3


def timeline_svg(era: Era, direction: Direction) -> str:
    """Numbered arrows on a date axis, with the breakthrough marked."""
    width, pad_l, pad_r = 1040, 60, 150
    row_step, half_h = 34, 14
    dash_top, label_block = 12, 36          # room for the breakthrough caption
    span_days = max((era.end - era.start).days, 1)

    def x_of(ts: pd.Timestamp) -> float:
        return pad_l + (ts - era.start).days / span_days * (width - pad_l - pad_r)

    xs = [x_of(ts) for ts in era.routes["first_ascent"]]
    rows = stack_rows(xs, min_gap=31.0)     # the arrow is a shade wider than the dot
    top_row = max(rows) if rows else 0
    # the canvas is only as tall as the tallest stack needs it to be
    axis_y = dash_top + label_block + half_h + top_row * row_step + 27
    height = axis_y + 44
    lift = axis_y - dash_top

    parts: list[str] = []

    # the era that follows, as a tinted strip past the breakthrough
    bx = x_of(era.end)
    parts.append(
        f'<rect x="{bx:.1f}" y="{dash_top:.1f}" '
        f'width="{width - pad_r * .55 - bx:.1f}" height="{lift:.1f}" '
        f'fill="#e8a33d" opacity="0.07"/>'
    )

    # axis
    parts.append(f'<line x1="{pad_l - 24}" y1="{axis_y}" '
                 f'x2="{width - pad_r * .55:.1f}" y2="{axis_y}" '
                 f'stroke="#4a4844" stroke-width="1"/>')

    # year ticks, or month-scale endpoints when the era is very short
    # ...skipping any that would sit under the breakthrough's own date label
    ticks = [t for t in pd.date_range(era.start.normalize(), era.end, freq="YS")
             if pad_l - 20 <= x_of(t) <= width - pad_r * .6
             and abs(x_of(t) - x_of(era.end)) > 46]
    if len(ticks) >= 2:
        for t in ticks:
            tx = x_of(t)
            parts.append(
                f'<line x1="{tx:.1f}" y1="{axis_y - 5}" x2="{tx:.1f}" '
                f'y2="{axis_y + 5}" stroke="#4a4844"/>'
                f'<text x="{tx:.1f}" y="{axis_y + 24}" text-anchor="middle" '
                f'fill="#8d8a84" font-size="12">{t.year}</text>')
    else:
        parts.append(
            f'<text x="{pad_l:.1f}" y="{axis_y + 24}" text-anchor="middle" '
            f'fill="#8d8a84" font-size="12">'
            f'{esc(era.start.strftime("%b %Y"))}</text>')

    # the breakthrough marker
    label = f"First {era.next_grade}" if era.next_grade else "no 9c+ yet"
    sub = era.breakthrough or f"as of {era.end.strftime('%b %Y')}"
    parts.append(
        f'<line x1="{bx:.1f}" y1="{dash_top:.1f}" x2="{bx:.1f}" '
        f'y2="{axis_y:.1f}" stroke="#e8a33d" stroke-width="2" '
        f'stroke-dasharray="6 5"/>'
        f'<text x="{bx + 9:.1f}" y="{dash_top + 12:.1f}" fill="#e8a33d" '
        f'font-size="14" font-weight="700">{esc(label)}</text>'
        f'<text x="{bx + 9:.1f}" y="{dash_top + 30:.1f}" fill="#c8a06a" '
        f'font-size="12.5">{esc(sub)}</text>'
        f'<text x="{bx:.1f}" y="{axis_y + 24}" text-anchor="middle" '
        f'fill="#e8a33d" font-size="12" font-weight="700">'
        f'{esc(era.end.strftime("%b %Y"))}</text>')

    # one numbered arrow per regrade
    for n, ((_, r), cx, row) in enumerate(
            zip(era.routes.iterrows(), xs, rows), start=1):
        cy = axis_y - 27 - row * row_step
        tip = (f"{r['climb_name']} — {r['suggested_clean']} "
               f"{'up' if direction.up else 'down'} to {r['grade_clean']}, "
               f"{r['first_climber']}, {r['first_ascent_date']}")
        parts.append(
            f'<g><polygon points="{arrow_points(cx, cy, direction.up)}" '
            f'fill="{direction.ink}" stroke="#0e0e0f" stroke-width="2" '
            f'stroke-linejoin="round"/>'
            f'<text x="{cx:.1f}" y="{number_baseline(cy, direction.up):.1f}" '
            f'text-anchor="middle" fill="#f2f0ec" font-size="12" '
            f'font-weight="700">{n}</text>'
            f'<title>{esc(tip)}</title></g>')

    return (f'<div class="chart"><svg viewBox="0 0 {width} {height}" '
            f'width="100%" height="{height}" role="img" '
            f'aria-label="{esc(direction.noun.capitalize())} among routes '
            f'first climbed in the {esc(era.grade)} era">'
            f'{"".join(parts)}</svg></div>')


def frontier_split(era: Era, ordinal=french_ordinal) -> tuple[int, int]:
    """How many of an era's regrades touched the hardest grade then climbed.

    One rule for both directions: the move has an end at or above the era's
    own grade. For an upgrade that means it arrived at the ceiling; for a
    downgrade, that it was claimed there or above it and then cut back.

    Nothing in the data settles *above* its era's ceiling — a route that did
    would have moved the ceiling itself — so "at or above" and "at" pick the
    same upgrades. The inequality is there for the downgrades, where a 9b
    claim made inside the 9a+ era is exactly the case worth seeing.

    ``ordinal`` is the scale's ranking function, so the boulder page can pass
    :func:`~sportgradehistory.grades.font_ordinal` and get the same rule read
    against Font grades.
    """
    if not len(era.routes):
        return 0, 0
    ceiling = ordinal(era.grade)
    reach = era.routes[["suggested_order", "grade_order"]].max(axis=1)
    return int((reach >= ceiling).sum()), len(era.routes)


def bar_path(x: float, w: float, base_y: float, length: float, up: bool,
             round_end: bool = True) -> str:
    """One bar segment: square at ``base_y``, 4px rounded at the far end.

    A segment with another stacked beyond it keeps both ends square — the 2px
    surface gap is what separates them, not a stroke or a rounded shoulder.
    """
    end = base_y - length if up else base_y + length
    if not round_end:
        return (f"M{x:.1f},{base_y:.1f} V{end:.1f} H{x + w:.1f} "
                f"V{base_y:.1f} Z")
    r = min(4.0, abs(length))
    near = end + r if up else end - r
    return (f"M{x:.1f},{base_y:.1f} V{near:.1f} "
            f"Q{x:.1f},{end:.1f} {x + r:.1f},{end:.1f} "
            f"H{x + w - r:.1f} Q{x + w:.1f},{end:.1f} {x + w:.1f},{near:.1f} "
            f"V{base_y:.1f} Z")


def overview_svg(up_eras: list[Era], down_eras: list[Era],
                 ordinal=french_ordinal, link: bool = True) -> str:
    """Both directions against one category axis, as a diverging bar chart.

    The arms grow away from a central gutter carrying the grade labels — up
    above, down below — so the chart speaks the same arrow language as the
    marks below it, and no label loses its band. One shared scale, so five up
    and five down draw the same length.

    Each bar is split: the moves that touched the era's top grade sit on the
    gutter in the lighter step, the rest carry on beyond them in the base ink.
    Putting the lighter part at the baseline is the point — every era's
    frontier count is then measured from the same line and can be read across
    the chart at a glance.

    ``ordinal`` is the grade scale in play. ``link`` makes each band a link to
    that era's own section; the boulder page carries the chart alone, with no
    sections to land on, so it turns the links off rather than shipping ten
    anchors that go nowhere.
    """
    width, pad_l, pad_r = 1040, 56, 20
    bar_w, gutter_h = 24.0, 26.0
    legend_y, label_gap, seg_gap = 24.0, 15.0, 2.0

    grades = [e.grade for e in up_eras]
    ups = [len(e.routes) for e in up_eras]
    downs = [len(e.routes) for e in down_eras]

    # 8px per move as long as that keeps the longer arm inside ARM_MAX; past
    # that the unit shrinks instead of the chart growing, because a 24px-wide
    # bar 344px long stops reading as a bar. Sport's tallest arm is 23, so it
    # never leaves the 8px case; boulder's is 43 and does.
    unit = min(8.0, ARM_MAX / max(max(ups), max(downs), 1))
    front = {d.key: [frontier_split(e, ordinal)[0] for e in eras]
             for d, eras in ((UPGRADES, up_eras), (DOWNGRADES, down_eras))}
    band = (width - pad_l - pad_r) / len(grades)

    gutter_top = legend_y + 22 + label_gap + max(ups) * unit
    gutter_bot = gutter_top + gutter_h
    floor = gutter_bot + max(downs) * unit
    height = floor + label_gap + 14

    parts: list[str] = []

    # legend — the swatch is the mark itself, so identity never rests on hue
    for i, (up, word, ink) in enumerate(
            ((True, "upgrades", UP_INK), (False, "downgrades", DOWN_INK))):
        lx = pad_l + 8 + i * 128
        parts.append(
            f'<polygon points="{arrow_points(lx, legend_y, up, 0.5)}" '
            f'fill="{ink}"/>'
            f'<text x="{lx + 13:.1f}" y="{legend_y + 4.5:.1f}" fill="#8d8a84" '
            f'font-size="12.5">{word}</text>')
    # the shading rule holds for both hues, so it is worded rather than
    # swatched: a sample in one of the two inks would read as that series only
    parts.append(
        f'<text x="{pad_l + 330}" y="{legend_y + 4.5:.1f}" fill="#8d8a84" '
        f'font-size="12.5">lighter: the move touched the era’s top '
        f'grade</text>')

    # gridlines every five routes on both arms, then the gutter's own edges
    for arm, base, sign in ((ups, gutter_top, -1), (downs, gutter_bot, 1)):
        for n in range(5, max(arm) + 1, 5):
            y = base + sign * n * unit
            parts.append(
                f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" '
                f'y2="{y:.1f}" stroke="#2c2c2a"/>'
                f'<text x="{pad_l - 10}" y="{y + 4:.1f}" text-anchor="end" '
                f'fill="#66635e" font-size="11">{n}</text>')
    for y in (gutter_top, gutter_bot):
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" '
                     f'y2="{y:.1f}" stroke="#4a4844" stroke-width="1"/>')

    # one band per era: two split bars, their values, the grade, a hit target
    for i, (grade, u, d) in enumerate(zip(grades, ups, downs)):
        cx = pad_l + (i + 0.5) * band
        bx = cx - bar_w / 2
        fu, fd = front[UPGRADES.key][i], front[DOWNGRADES.key][i]
        band_parts = [
            f'<rect class="hit" x="{pad_l + i * band:.1f}" '
            f'y="{legend_y + 22:.1f}" width="{band:.1f}" '
            f'height="{floor - legend_y - 22 + label_gap:.1f}"/>']

        for n, f, up, ink, lit, base in (
                (u, fu, True, UP_INK, UP_FRONTIER_INK, gutter_top),
                (d, fd, False, DOWN_INK, DOWN_FRONTIER_INK, gutter_bot)):
            sign = -1 if up else 1
            rest = n - f
            if f:
                band_parts.append(
                    f'<path d="{bar_path(bx, bar_w, base, f * unit, up, not rest)}" '
                    f'fill="{lit}"/>')
            if rest:
                # the 2px gap is taken out of this segment, so the bar still
                # ends at the full count
                gap = seg_gap if f else 0.0
                band_parts.append(
                    f'<path d="{bar_path(bx, bar_w, base + sign * (f * unit + gap), rest * unit - gap, up)}" '
                    f'fill="{ink}"/>')
            # the total sits at the bar's end; a zero still gets a mark, in
            # dim ink, so an empty era reads as counted rather than missing
            ly = base - n * unit - 7 if up else base + n * unit + 16
            band_parts.append(
                f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'fill="{"#f2f0ec" if n else "#66635e"}" font-size="12" '
                f'font-weight="{700 if n else 400}">{n}</text>')
            # and the frontier count beside its own segment — only when there
            # is a faded part to tell it from, since an all-solid bar already
            # says it with the end label
            if f and rest:
                band_parts.append(
                    f'<text x="{bx + bar_w + 5:.1f}" '
                    f'y="{base + sign * f * unit / 2 + 4:.1f}" fill="#f2f0ec" '
                    f'font-size="11" font-weight="700">{f}</text>')

        band_parts.append(
            f'<text x="{cx:.1f}" y="{gutter_top + 17.5:.1f}" '
            f'text-anchor="middle" fill="#cfcbc3" font-size="12" '
            f'font-weight="700">{esc(grade)}</text>'
            f'<title>{esc(grade)} era — {plural(u, "upgrade")}, {fu} touching '
            f'{esc(grade)}; {plural(d, "downgrade")}, {fd} touching '
            f'{esc(grade)}</title>')
        band_g = f'<g class="band">{"".join(band_parts)}</g>'
        parts.append(
            f'<a href="#{grade.replace("+", "-plus")}">{band_g}</a>'
            if link else band_g)

    return (f'<div class="chart"><svg viewBox="0 0 {width} {height:.0f}" '
            f'width="100%" height="{height:.0f}" role="img" '
            f'aria-label="Upgrades and downgrades per grade era, with the '
            f'moves that touched the era’s top grade called out: '
            + "; ".join(
                f"{g} {u} up ({fu} at {g}), {d} down ({fd} at {g})"
                for g, u, d, fu, fd in zip(grades, ups, downs,
                                           front[UPGRADES.key],
                                           front[DOWNGRADES.key]))
            + f'">{"".join(parts)}</svg></div>')


def overview_section(up_eras: list[Era], down_eras: list[Era]) -> str:
    ups = [len(e.routes) for e in up_eras]
    downs = [len(e.routes) for e in down_eras]
    fr_up = [frontier_split(e)[0] for e in up_eras]
    fr_down = [frontier_split(e)[0] for e in down_eras]
    by_span = sorted(up_eras, key=lambda e: e.years)
    peak = up_eras[fr_up.index(max(fr_up))]
    total, frontier = sum(ups) + sum(downs), sum(fr_up) + sum(fr_down)
    # the eras that recorded moves but none at their own ceiling, in order —
    # the run of them at the end of the timeline is the story worth naming
    quiet = [e.grade for e, fu, fd in zip(up_eras, fr_up, fr_down)
             if len(e.routes) and not fu and not fd]
    since = (f"; since {esc(quiet[0])} the frontier has taken none at all, "
             f"and every recorded move has been in the backlog below it"
             if quiet else "")
    return (
        '<section id="overview">'
        '<div class="head"><h2>Both directions, era by era</h2>'
        f'<span class="sub">{sum(ups)} up and {sum(downs)} down across the '
        f'ten eras, {frontier} of them at the frontier</span></div>'
        + overview_svg(up_eras, down_eras)
        + f'<p class="note">The lighter part of each bar is the moves that '
          f'touched the era&rsquo;s own top grade — an upgrade that arrived at the '
          f'ceiling, or a downgrade claimed at or above it and then cut back. '
          f'Only {frontier} of the {total} moves qualify, {max(fr_up)} of '
          f'them in the {esc(peak.grade)} era alone{since}.</p>'
          f'<p class="note">Counts, not rates: the eras run from '
          f'{span_label(by_span[0].years).lstrip("~")} '
          f'({esc(by_span[0].grade)}) to '
          f'{span_label(by_span[-1].years).lstrip("~")} '
          f'({esc(by_span[-1].grade)}), so a tall bar can mean a long era as '
          f'much as a busy one. Both arms share one scale, and the lighter '
          f'parts sit on the gutter so they can be compared across eras. '
          f'Click a band for that era&rsquo;s routes; hover for the split.</p>'
          '</section>')


def route_list(era: Era, direction: Direction) -> str:
    items = []
    for _, r in era.routes.iterrows():
        items.append(
            f'<li><a href="{esc(r["climb_url"])}">{esc(r["climb_name"])}</a> '
            f'<span class="move">{esc(r["suggested_clean"])} '
            f'<b>{direction.glyph}</b> {esc(r["grade_clean"])}</span> — '
            f'{esc(r["first_ascent_date"])}<br>'
            f'<span class="who">{esc(r["first_climber"])}</span></li>')
    return f'<ol class="routes">{"".join(items)}</ol>'


def tiles(era: Era, direction: Direction) -> str:
    n = len(era.routes)
    if era.open_era:
        second = ("First 9c &rarr; today", span_label(era.years),
                  "and still open")
        third = ("Grade breakthrough", "none yet",
                 f"as of {era.end.strftime('%d %b %Y')}")
    else:
        second = (f"First {esc(era.grade)} &rarr; first {esc(era.next_grade)}",
                  span_label(era.years), "")
        third = ("Grade breakthrough", esc(era.breakthrough),
                 era.end.strftime("%d %b %Y"))
    cells = [
        (f"{direction.noun.capitalize()} in the {esc(era.grade)} era", str(n),
         f"{plural(n, 'route')} {direction.verb}"),
        second, third,
    ]
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="k">{k}</div>'
        f'<div class="v">{v}{f"<small>{s}</small>" if s else ""}</div></div>'
        for k, v, s in cells) + "</div>"


def section(era: Era, direction: Direction) -> str:
    anchor = era.grade.replace("+", "-plus")
    if era.open_era:
        sub = (f"first climbed since Silence — the era is still open after "
               f"{span_label(era.years).lstrip('~')}")
    else:
        sub = (f"first climbed before {esc(era.breakthrough)} became the "
               f"first {esc(era.next_grade)}")

    if len(era.routes):
        detail = (
            route_list(era, direction)
            + timeline_svg(era, direction)
            + f'<p class="note">Arrows are placed by first-ascent date and '
              f'stacked when they crowd; year-only dates sit at 1 January, so '
              f'the left edge of a cluster can be soft. Hover an arrow for the '
              f'route and the move.</p>')
    else:
        detail = (f'<p class="empty">No {direction.noun} are recorded for '
                  f'routes first climbed in this era. The source carries a '
                  f'grade suggestion for very few ascents this early, so read '
                  f'this as nothing recorded rather than nothing moved.</p>')

    return (f'<section id="{anchor}" class="{"up" if direction.up else "down"}">'
            f'<div class="head"><h2><span class="era">{esc(era.grade)}</span> '
            f'era</h2><span class="sub">{sub}</span></div>'
            f'{tiles(era, direction)}{detail}</section>')


def build_page(eras: list[Era], direction: Direction, overview: str) -> None:
    chips = "".join(
        f'<a href="#{e.grade.replace("+", "-plus")}">{esc(e.grade)} '
        f'<b>{len(e.routes)}</b></a>' for e in eras)
    body = "".join(section(e, direction) for e in eras)
    counts = ", ".join(f"{e.grade} {len(e.routes)}" for e in eras)
    total = sum(len(e.routes) for e in eras)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(direction.title)}</title>
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body><main>
<nav class="top"><a href="index.html">&larr; all timelines</a> &middot;
<a href="runway-by-grade.html">the runway page</a></nav>
<h1>{esc(direction.heading)}</h1>
<p>The same windows as the runway page — each era runs from the breakthrough
that opened it to the one that closed it — but a different question. Not what
was established at the top grade, but which routes climbed during the era were
later judged {esc(direction.comparative)} than the first ascentionist
said: {total} of them, at every grade, not only at the ceiling.</p>
<p>A route is placed by when it was <em>climbed</em>, not by when opinion
turned, because the turn has no date in the record. Its move is read as the
first ascentionist's suggestion against today's consensus. That field is
sparse at the source, so every count here is a floor, not a census — and an
era with none recorded is kept on the page rather than dropped, because the
gap is in the record, not in the climbing.</p>
{overview}
<div class="chips">{chips}</div>
{body}
<footer>{esc(direction.noun.capitalize())} by era: {esc(counts)} &middot;
Data: <a href="https://climbing-history.org">climbing-history.org</a>,
scraped 2026-09-09 &middot; <code>as_consensus</code> against the recorded
suggestion &middot; routes match
<code>data/processed/regraded_routes.csv</code> and the per-era tables in
<code>visualizations/grade-changes/</code> &middot; part of
<a href="https://github.com/joeykang21-arch">sport-grade-history</a></footer>
</main></body>
</html>"""

    out = VIZ_DIR / direction.filename
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out}")
    for e in eras:
        print(f"  {e.grade:>4} {direction.key:>9}s: {len(e.routes):>3}")


def build() -> None:
    sport = load_sport()
    regraded = load_regrades()

    # Both pages open on the same overview, built once: it is a comparison of
    # the two directions, so it would be the same chart either way.
    eras = {d.key: collect_eras(sport, regraded, d)
            for d in (UPGRADES, DOWNGRADES)}
    overview = overview_section(eras[UPGRADES.key], eras[DOWNGRADES.key])

    for direction in (UPGRADES, DOWNGRADES):
        build_page(eras[direction.key], direction, overview)


def main() -> None:
    build()


if __name__ == "__main__":
    main()
