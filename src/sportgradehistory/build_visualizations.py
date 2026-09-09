"""Generate the static HTML pages in ``visualizations/``.

One page per grade era (the reign of each top grade, `as_consensus`), plus the
upgrades and downgrades recorded within each era, and an index linking them.
The pages are plain self-contained HTML — inline CSS, inline SVG, native
``<title>`` tooltips, no JavaScript dependencies and no build step — so they
work opened from disk and served over GitHub Pages alike, matching the boulder
repo's convention.

Run as::

    python -m sportgradehistory.build_visualizations
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from . import config
from .grades import french_ordinal
from .milestones import breakthrough_table, load_sport

VIZ_DIR = config.ROOT / "visualizations"

# The repo's validated palette (see notebooks): light surface, blue accent,
# orange for proposed-grade context, red reserved for disputed status.
CSS = """
:root { color-scheme: light; }
body { margin: 0; background: #fcfcfb; color: #0b0b0b;
       font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
h1 { font-size: 1.7rem; margin: 0 0 .3rem; }
h2 { font-size: 1.15rem; margin: 2.2rem 0 .6rem; }
p  { max-width: 70ch; }
.muted { color: #52514e; }
.small { font-size: .85rem; }
a { color: #2a78d6; }
nav a { margin-right: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; padding: .35rem .6rem;
         border-bottom: 1px solid #e5e4e0; }
th { color: #52514e; font-weight: 600; }
tr:hover td { background: #f2f1ee; }
.chart { overflow-x: auto; margin: 1rem 0; }
.tag { display: inline-block; padding: .05rem .5rem; border-radius: 999px;
       font-size: .78rem; border: 1px solid #e5e4e0; color: #52514e; }
.tag.up { color: #1a7a4f; border-color: #1a7a4f; }
.tag.down { color: #b3391f; border-color: #b3391f; }
.tag.disputed { color: #e34948; border-color: #e34948; }
ul.pages { list-style: none; padding: 0; }
ul.pages li { margin: .35rem 0; }
footer { margin-top: 3rem; font-size: .8rem; color: #52514e; }
"""


def slug(grade: str) -> str:
    return grade.replace("+", "-plus")


def plural(n: int) -> str:
    """``"1 route"`` / ``"5 routes"`` -- several eras contain exactly one."""
    return f"{n} route" if n == 1 else f"{n} routes"


def page(title: str, body: str, depth: int = 1) -> str:
    home = "../" * depth + "index.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body><main>
<nav class="small"><a href="{home}">&larr; all timelines</a></nav>
{body}
<footer>Data: <a href="https://climbing-history.org">climbing-history.org</a>,
scraped 2026-09-09 &middot; grades shown are today's consensus
(<code>as_consensus</code>) unless marked &middot; part of
<a href="https://github.com/joeykang21-arch">sport-grade-history</a></footer>
</main></body>
</html>"""


def era_svg(routes: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
            milestone_name: str) -> str:
    """An inline SVG timeline: one dot per FA, native tooltips, no JS."""
    width, height, pad = 900, 220, 40
    span = max((end - start).days, 1)

    def x(ts: pd.Timestamp) -> float:
        return pad + (ts - start).days / span * (width - 2 * pad)

    dots = []
    for i, (_, r) in enumerate(routes.iterrows()):
        cy = 60 + (i % 8) * 16
        label = (f"{r['climb_name']} — {r['grade_clean']}, "
                 f"{r['first_climber'] or 'FA unknown'}, "
                 f"{r['first_ascent_date'] or 'date unknown'}")
        accent = r["climb_name"] == milestone_name
        dots.append(
            f'<circle cx="{x(r["first_ascent"]):.1f}" cy="{cy}" '
            f'r="{7 if accent else 5}" '
            f'fill="{"#2a78d6" if accent else "#b8c4d4"}" '
            f'stroke="#fcfcfb" stroke-width="1.5">'
            f"<title>{html.escape(label)}</title></circle>"
        )

    years = pd.date_range(start, end, freq="YS")
    ticks = "".join(
        f'<line x1="{x(t):.1f}" y1="40" x2="{x(t):.1f}" y2="190" '
        f'stroke="#e5e4e0"/>'
        f'<text x="{x(t):.1f}" y="208" text-anchor="middle" '
        f'fill="#52514e" font-size="11">{t.year}</text>'
        for t in years if pad <= x(t) <= width - pad
    )

    return (f'<div class="chart"><svg viewBox="0 0 {width} {height}" '
            f'width="{width}" role="img" '
            f'aria-label="Timeline of first ascents in this era">'
            f'{ticks}{"".join(dots)}</svg>'
            f'<p class="small muted">One dot per first ascent at the era&rsquo;s top '
            f'grade; the blue dot is the route that opened the era. Hover a dot '
            f'for the route.</p></div>')


def route_table(routes: pd.DataFrame, extra_status: bool = True) -> str:
    rows = []
    for _, r in routes.iterrows():
        status = ""
        if extra_status and r.get("status") not in (None, "consensus"):
            css = "disputed" if r["status"] == "disputed" else ""
            status = f' <span class="tag {css}">{r["status"]}</span>'
        date = r["first_ascent_date"] if pd.notna(r["first_ascent_date"]) else "—"
        climber = r["first_climber"] if pd.notna(r["first_climber"]) else "—"
        rows.append(
            "<tr>"
            f"<td><a href=\"{html.escape(str(r['climb_url']))}\">"
            f"{html.escape(str(r['climb_name']))}</a>{status}</td>"
            f"<td>{r['grade_clean']}</td>"
            f"<td>{html.escape(str(climber))}</td>"
            f"<td>{html.escape(str(date))}</td>"
            f"<td>{r['num_ascents']}</td></tr>"
        )
    return ("<table><thead><tr><th>Route</th><th>Grade</th><th>First ascent"
            "</th><th>Date</th><th># ascents</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def build() -> None:
    sport = load_sport()
    consensus = breakthrough_table(sport, "as_consensus")
    regraded = pd.read_csv(config.REGRADED_ROUTES_CSV, encoding="utf-8")
    regraded["first_ascent"] = pd.to_datetime(regraded["first_ascent"])

    eras_dir = VIZ_DIR / "grade-eras"
    changes_dir = VIZ_DIR / "grade-changes"
    eras_dir.mkdir(parents=True, exist_ok=True)
    changes_dir.mkdir(parents=True, exist_ok=True)

    scrape_end = pd.Timestamp("2026-09-09")
    era_links, change_links = [], []

    bounds = list(consensus["first_ascent"]) + [scrape_end]
    for i, (_, m) in enumerate(consensus.iterrows()):
        grade = m["grade"]
        start, end = bounds[i], bounds[i + 1]
        nxt = consensus.iloc[i + 1] if i + 1 < len(consensus) else None

        during = sport[
            (sport["grade_clean"] == grade)
            & sport["first_ascent"].notna()
            & (sport["first_ascent"] >= start)
            & (sport["first_ascent"] < end)
        ].sort_values("first_ascent")

        if nxt is not None:
            fname = f"{slug(grade)}-to-{slug(nxt['grade'])}.html"
            title = f"The {grade} era, {start.year}–{end.year}"
            closer = (f"<p>The era closed when <strong>{html.escape(nxt['route'])}"
                      f"</strong> brought {nxt['grade']} in "
                      f"{nxt['first_ascent'].year}.</p>")
        else:
            fname = f"{slug(grade)}-era.html"
            title = f"The {grade} era, {start.year}–present"
            closer = ("<p>The era is still open: no route has yet brought "
                      "the next grade.</p>")

        # An era shorter than a year is the interesting case, not a typo: the
        # consensus reading puts Liquid Ambar and Hubble eleven weeks apart in
        # 1990, so "1990-1990" needs saying out loud.
        days = (end - start).days
        duration = ""
        if days < 365:
            weeks = round(days / 7)
            duration = (f'<p class="small muted">This era lasted just '
                        f'<strong>{weeks} weeks</strong> — the shortest in the '
                        f'sport&rsquo;s history, and an artefact of consensus: '
                        f'both routes were first climbed in 1990 and regraded '
                        f'later.</p>')

        tie = ""
        if pd.notna(m.get("ordering_unresolved_with")):
            tie = (f'<p class="small muted">Ordering note: '
                   f'{html.escape(str(m["ordering_unresolved_with"]))} shares '
                   f'the year and the data cannot rank them; this page follows '
                   f'the anchored date.</p>')

        body = (
            f"<h1>{html.escape(title)}</h1>"
            f"<p class='muted'>Opened by <strong>{html.escape(m['route'])}"
            f"</strong> ({html.escape(str(m['climber']))}, "
            f"{m['first_ascent'].year}) — the first {grade} by today's "
            f"consensus.</p>{duration}{tie}"
            + era_svg(during, start, end, m["route"])
            + f"<h2>The {plural(len(during))} of {grade} established during "
              f"the era</h2>"
            + route_table(during)
            + closer
        )
        (eras_dir / fname).write_text(page(title, body), encoding="utf-8")
        era_links.append((fname, title, len(during)))

        # Regrades whose FA falls inside the era window.
        in_era = regraded[
            regraded["first_ascent"].notna()
            & (regraded["first_ascent"] >= start)
            & (regraded["first_ascent"] < end)
        ]
        for direction in ("upgrade", "downgrade"):
            sub = in_era[in_era["direction"] == direction].sort_values("first_ascent")
            if sub.empty:
                continue
            cname = f"{slug(grade)}-era-{direction}s.html"
            ctitle = f"{direction.title()}s of the {grade} era"
            rows = "".join(
                "<tr>"
                f"<td><a href=\"{html.escape(str(r['climb_url']))}\">"
                f"{html.escape(str(r['climb_name']))}</a></td>"
                f"<td>{r['suggested_clean']} &rarr; {r['grade_clean']} "
                f"<span class='tag {'up' if direction == 'upgrade' else 'down'}'>"
                f"{direction}</span></td>"
                f"<td>{html.escape(str(r['first_climber']))}</td>"
                f"<td>{html.escape(str(r['first_ascent_date']))}</td></tr>"
                for _, r in sub.iterrows()
            )
            cbody = (
                f"<h1>{html.escape(ctitle)}</h1>"
                f"<p class='muted'>Routes first climbed during the {grade} era "
                f"({start.year}–{end.year if nxt is not None else 'present'}) "
                f"whose consensus grade later moved off the first "
                f"ascentionist's suggestion. The suggestion field is sparse on "
                f"the source site, so this is a floor, not a census.</p>"
                "<table><thead><tr><th>Route</th><th>Grade moved</th>"
                "<th>First ascent</th><th>Date</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
            (changes_dir / cname).write_text(page(ctitle, cbody), encoding="utf-8")
            change_links.append((cname, ctitle, len(sub)))

    era_list = "".join(
        f'<li><a href="grade-eras/{f}">{html.escape(t)}</a> '
        f'<span class="muted small">({plural(n)})</span></li>'
        for f, t, n in era_links
    )
    change_list = "".join(
        f'<li><a href="grade-changes/{f}">{html.escape(t)}</a> '
        f'<span class="muted small">({plural(n)})</span></li>'
        for f, t, n in change_links
    )
    index_body = f"""
<h1>Sport grade history — interactive timelines</h1>
<p>One page per grade era from 8a+ (1983) to the present, built from the
2026-09-09 scrape of climbing-history.org. Grades shown are today's consensus;
the repo's notebooks carry the parallel <code>as_proposed</code> reading and
the disputed claims (Akira, Chilam Balam), which these pages exclude.</p>
<h2>Grade eras</h2><ul class="pages">{era_list}</ul>
<h2>Upgrades and downgrades within each era</h2>
<p class="small muted">Reconstructed from the first ascentionist's recorded
grade suggestion — sparse at the source, so floors, not censuses.</p>
<ul class="pages">{change_list}</ul>
"""
    (VIZ_DIR / "index.html").write_text(
        page("Sport grade history — timelines", index_body, depth=0)
        .replace('<nav class="small"><a href="index.html">&larr; all timelines</a></nav>', ""),
        encoding="utf-8",
    )

    print(f"wrote {len(era_links)} era pages, {len(change_links)} change pages, "
          f"and index.html -> {VIZ_DIR}")


def main() -> None:
    build()


if __name__ == "__main__":
    main()
