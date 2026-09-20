"""Generate ``visualizations/runway-by-grade.html``.

One section per grade: every route established at that grade *before the next
grade arrived* — the runway — as a numbered list and a numbered timeline, with
the breakthrough that closed the era marked on it.

``era_runway_volumes.csv`` (notebook 03) carries the counts; this page carries
the routes behind them, which is what makes a count of three at 9b+ read
differently from a count of eighteen at 9a+.

Grades are ``as_consensus`` throughout. Disputed claims (Akira, Chilam Balam)
are drawn, because they sat on the runway at the time and excluding them would
silently change a count, but they are marked as disputed wherever they appear.

Self-contained HTML: inline CSS, inline SVG, no JavaScript, no build step —
same convention as ``build_visualizations.py``.

Run as::

    python -m sportgradehistory.build_runway_pages
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import pandas as pd

from . import config
from .grades import FRENCH_SCALE
from .milestones import breakthrough_table, load_sport

VIZ_DIR = config.ROOT / "visualizations"
SCRAPE_DATE = pd.Timestamp("2026-09-09")

CSS = """
:root {
  color-scheme: dark;
  --bg: #0e0e0f;
  --ink: #f2f0ec;
  --muted: #8d8a84;
  --dim: #66635e;
  --accent: #e8a33d;
  --dot: #3b82d6;
  --dot-ink: #f2f0ec;
  --disputed: #e0574f;
  --panel: #17171a;
  --rule: #34322f;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
h1 { font-size: 1.6rem; margin: 0 0 .4rem; }
h2 { font-size: 1.25rem; margin: 0; }
p { color: var(--muted); max-width: 74ch; }
a { color: var(--accent); }
nav.top { font-size: .85rem; margin-bottom: 1rem; }
code { color: #cfcbc3; }

.chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: 1.6rem 0 .5rem;
         padding: .8rem 0; border-top: 1px solid var(--rule);
         border-bottom: 1px solid var(--rule); }
.chips a { display: inline-block; padding: .2rem .7rem; border-radius: 999px;
           border: 1px solid var(--rule); color: var(--muted);
           text-decoration: none; font-size: .82rem; }
.chips a:hover { color: var(--ink); border-color: var(--muted); }
.chips a b { color: var(--accent); font-weight: 700; }

section { padding: 2.4rem 0 1rem; border-bottom: 1px solid var(--rule); }
.head { display: flex; align-items: baseline; gap: .7rem; flex-wrap: wrap; }
.head .era { color: var(--accent); font-weight: 700; }
.head .sub { color: var(--muted); font-size: .88rem; }

.tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem;
         margin: 1.1rem 0 .2rem; }
.tile { background: var(--panel); border: 1px solid var(--rule);
        border-radius: 6px; padding: .7rem .9rem; text-align: center; }
.tile .k { font-size: .72rem; color: var(--muted); letter-spacing: .02em; }
.tile .v { font-size: 1.45rem; font-weight: 700; margin-top: .15rem; }
.tile .v small { font-size: .8rem; font-weight: 400; color: var(--muted);
                 display: block; margin-top: .1rem; }

ol.routes { columns: 2; column-gap: 2.5rem; list-style: none;
            padding: 0; margin: 1.2rem 0 .4rem; counter-reset: r; }
ol.routes li { counter-increment: r; break-inside: avoid; margin: .3rem 0;
               font-size: .92rem; padding-left: 2rem; text-indent: -2rem; }
ol.routes li::before { content: counter(r) ". "; color: var(--accent);
                       font-variant-numeric: tabular-nums; }
ol.routes .who { color: var(--muted); font-size: .85rem; }
ol.routes .flag { color: var(--disputed); font-size: .78rem; }

.chart { overflow-x: auto; margin: .6rem 0 0; }
.chart svg { display: block; min-width: 720px; }
.note { font-size: .8rem; color: var(--dim); margin: .3rem 0 0; }

footer { margin-top: 2.5rem; font-size: .8rem; color: var(--muted); }
@media (max-width: 720px) {
  ol.routes { columns: 1; }
  .tiles { grid-template-columns: 1fr; }
}
"""


@dataclass
class Era:
    grade: str                    # the grade the runway is made of
    next_grade: str | None        # the grade that ended it (None = still open)
    start: pd.Timestamp           # first ascent at `grade`
    end: pd.Timestamp             # the breakthrough, or the scrape date
    breakthrough: str | None
    routes: pd.DataFrame
    open_era: bool = False

    @property
    def years(self) -> float:
        return (self.end - self.start).days / 365.25


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def span_label(years: float) -> str:
    if years < 1:
        months = max(round(years * 12), 1)
        return f"~{months} mo"
    return f"~{years:.1f} yrs"


def collect_eras(sport: pd.DataFrame) -> list[Era]:
    """One Era per milestone grade, each holding its own runway routes."""
    milestones = breakthrough_table(sport, "as_consensus")
    eras: list[Era] = []

    for i, row in milestones.iterrows():
        ordinal = row["grade_order"]
        is_last = i == len(milestones) - 1
        nxt = None if is_last else milestones.iloc[i + 1]
        end = SCRAPE_DATE if is_last else nxt["first_ascent"]

        runway = sport[
            (sport["grade_order"] == ordinal)
            & sport["first_ascent"].notna()
            & (sport["first_ascent"] < end)
        ].sort_values("first_ascent")

        eras.append(Era(
            grade=FRENCH_SCALE[int(ordinal)],
            next_grade=None if is_last else nxt["grade"],
            start=row["first_ascent"],
            end=end,
            breakthrough=None if is_last else nxt["route"],
            routes=runway,
            open_era=is_last,
        ))
    return eras


def stack_rows(xs: list[float], min_gap: float = 30.0) -> list[int]:
    """Assign each dot a row so neighbours never overlap; lowest row wins."""
    last_in_row: list[float] = []
    rows: list[int] = []
    for x in xs:
        for r, last in enumerate(last_in_row):
            if x - last >= min_gap:
                rows.append(r)
                last_in_row[r] = x
                break
        else:
            rows.append(len(last_in_row))
            last_in_row.append(x)
    return rows


def timeline_svg(era: Era) -> str:
    """Numbered dots on a date axis, with the breakthrough marked."""
    width, pad_l, pad_r = 1040, 60, 150
    row_step, radius = 32, 13
    dash_top, label_block = 12, 36          # room for the breakthrough caption
    # A runway can hold a route dated before the breakthrough that opens it:
    # the same-year tie rival (Les Mains Sales sits at 8b months before Kanal
    # im Rücken takes the grade). Draw from whichever comes first, or that
    # route lands off-canvas at a large negative x.
    earliest = era.routes["first_ascent"].min() if len(era.routes) else era.start
    domain_start = min(era.start, earliest) if pd.notna(earliest) else era.start
    span_days = max((era.end - domain_start).days, 1)

    def x_of(ts: pd.Timestamp) -> float:
        return pad_l + (ts - domain_start).days / span_days * (width - pad_l - pad_r)

    xs = [x_of(ts) for ts in era.routes["first_ascent"]]
    rows = stack_rows(xs)
    top_row = max(rows) if rows else 0
    # the canvas is only as tall as the tallest stack needs it to be
    axis_y = dash_top + label_block + radius + top_row * row_step + 26
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
    ticks = [t for t in pd.date_range(domain_start.normalize(), era.end, freq="YS")
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
            f'{esc(domain_start.strftime("%b %Y"))}</text>')

    # the breakthrough marker
    label = (f"First {era.next_grade}" if era.next_grade else "no 9c+ yet")
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

    # one numbered dot per route on the runway
    for n, ((_, r), cx, row) in enumerate(
            zip(era.routes.iterrows(), xs, rows), start=1):
        cy = axis_y - 26 - row * row_step
        disputed = r.get("status") == "disputed"
        fill = "#e0574f" if disputed else "#3b82d6"
        tip = (f"{r['climb_name']} — {r['grade_clean']}, "
               f"{r['first_climber'] or 'FA unknown'}, "
               f"{r['first_ascent_date'] or 'date unknown'}"
               + (" (disputed)" if disputed else ""))
        parts.append(
            f'<g><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" '
            f'fill="{fill}" stroke="#0e0e0f" stroke-width="2"/>'
            f'<text x="{cx:.1f}" y="{cy + 4.5:.1f}" text-anchor="middle" '
            f'fill="#f2f0ec" font-size="12" font-weight="700">{n}</text>'
            f'<title>{esc(tip)}</title></g>')

    return (f'<div class="chart"><svg viewBox="0 0 {width} {height}" '
            f'width="100%" height="{height}" role="img" '
            f'aria-label="Routes at {esc(era.grade)} before '
            f'{esc(era.next_grade or "the next grade")} arrived">'
            f'{"".join(parts)}</svg></div>')


def route_list(era: Era) -> str:
    items = []
    for _, r in era.routes.iterrows():
        disputed = r.get("status") == "disputed"
        flag = ' <span class="flag">disputed</span>' if disputed else ""
        when = esc(r["first_ascent_date"] or r["first_ascent"].date())
        items.append(
            f'<li><a href="{esc(r["climb_url"])}">{esc(r["climb_name"])}</a>'
            f'{flag} — {when}<br>'
            f'<span class="who">{esc(r["first_climber"] or "FA unknown")}</span>'
            f'</li>')
    return f'<ol class="routes">{"".join(items)}</ol>'


def tiles(era: Era) -> str:
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
        (f"Consensus {esc(era.grade)}s established", str(n),
         plural(n, "route") + " on the runway"),
        second, third,
    ]
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="k">{k}</div>'
        f'<div class="v">{v}{f"<small>{s}</small>" if s else ""}</div></div>'
        for k, v, s in cells) + "</div>"


def section(era: Era) -> str:
    anchor = era.grade.replace("+", "-plus")
    if era.open_era:
        sub = (f"every 9c so far — no 9c+ has arrived in "
               f"{span_label(era.years).lstrip('~')}")
    else:
        sub = (f"established before {esc(era.breakthrough)} became the first "
               f"{esc(era.next_grade)}")
    return (f'<section id="{anchor}">'
            f'<div class="head"><h2><span class="era">{esc(era.grade)}</span> '
            f'runway</h2><span class="sub">{sub}</span></div>'
            f'{tiles(era)}{route_list(era)}{timeline_svg(era)}'
            f'<p class="note">Dots are placed by first-ascent date and stacked '
            f'when they crowd; year-only dates sit at 1 January, so the left '
            f'edge of a cluster can be soft. Hover a dot for the route.</p>'
            f'</section>')


def build() -> None:
    sport = load_sport()
    eras = collect_eras(sport)

    chips = "".join(
        f'<a href="#{e.grade.replace("+", "-plus")}">{esc(e.grade)} '
        f'<b>{len(e.routes)}</b></a>' for e in eras)

    body = "".join(section(e) for e in eras)
    counts = ", ".join(f"{e.grade} {len(e.routes)}" for e in eras)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The runway before each new grade</title>
<style>{CSS}</style>
</head>
<body><main>
<nav class="top"><a href="index.html">&larr; all timelines</a></nav>
<h1>How much exists at a grade before the next one arrives</h1>
<p>For each grade, every route established at it <em>before</em> the first
route of the next grade — the runway. The count is the headline; the routes
are what the count is made of, which is why three at 9b+ reads differently
from eighteen at 9a+.</p>
<p>Grades are today's consensus, so a route counts on the runway of the grade
it holds <em>now</em>, not the one it was given. Disputed claims are drawn and
labelled rather than dropped: they stood on the runway at the time, and
removing them would quietly change a count.</p>
<div class="chips">{chips}</div>
{body}
<footer>Runway counts: {esc(counts)} &middot;
Data: <a href="https://climbing-history.org">climbing-history.org</a>,
scraped 2026-09-09 &middot; <code>as_consensus</code> &middot; counts match
<code>data/processed/era_runway_volumes.csv</code> &middot; part of
<a href="https://github.com/joeykang21-arch">sport-grade-history</a></footer>
</main></body>
</html>"""

    out = VIZ_DIR / "runway-by-grade.html"
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out}")
    for e in eras:
        print(f"  {e.grade:>4} runway: {plural(len(e.routes), 'route'):>9}, "
              f"{span_label(e.years)}"
              + ("" if e.open_era else f" -> {e.breakthrough}"))


def main() -> None:
    build()


if __name__ == "__main__":
    main()
