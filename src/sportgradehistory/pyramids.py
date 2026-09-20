"""First-ascent pyramids drawn on one shared scale.

Notebook 03 already draws the ten milestone climbers' FA pyramids, each panel
normalised to its own widest tier. That answers "what shape was it?" and
refuses to answer "how big was it?" — Moffatt's two 7c+s and Ondra's
twenty-six 9a's are drawn the same width, and the note under the figure says
so. This module is the other half: the same pyramids on **one** scale, so the
panels can be compared to each other directly.

Two things change to make that work.

*Grade moves to a shared vertical axis.* Every panel carries the same grade
ladder, so 9a sits at the same height everywhere and a gap in a pyramid is
visible as a gap. Self-normalised panels stack tiers from each pyramid's own
floor, which is what makes them incomparable even before the widths differ.

*Colour stops encoding grade.* It was redundant the moment grade got its own
axis, and it never validated anyway: thirteen steps of one blue ramp fail both
the adjacent-lightness check and the light-end contrast floor against this
figure's paper. The freed channel goes to something the pyramids could not say
before — whether each first ascent has been **repeated**. That varies enormously
between climbers (Ghisolfi 12% unrepeated, Bouin 81%) and it qualifies every
tier above 9a, where a grade is a proposal until someone else confirms it.

The tiers are drawn as centred bars rather than the tapering trapezoids of the
self-normalised figure. On a shared scale a sloped edge would put a tier's area
somewhere between its own count and its neighbour's, which is exactly the
reading the figure exists to make precise.

Run as::

    python -m sportgradehistory.pyramids
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from . import config
from .grades import FRENCH_SCALE, french_ordinal
from .milestones import breakthrough_table, load_sport

# The grade a pyramid starts counting at. 7c is two rungs under the first
# milestone (8a+), so the early pyramids have somewhere to stand.
FLOOR = "7c"

# The climbers the "today" panel is drawn for, in the order they are drawn.
# Spelled as asked for rather than as the site spells them — `_fold` makes the
# match accent-insensitive, which is the only difference that bites here
# (the site carries Jorge Díaz-Rullo with the accent).
TODAYS_CLIMBERS = [
    "Adam Ondra",
    "Seb Bouin",
    "Alex Megos",
    "Stefano Ghisolfi",
    "Jorge Diaz-Rullo",
    "Jakob Schubert",
    "Sean Bailey",
]

PAPER, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e5e4e0"

# Two steps of one blue: the dark for first ascents someone else has since
# repeated, the light for those still standing on the first ascentionist's word
# alone. Validated as an ordinal pair against this paper — monotone lightness,
# gap >= 0.06, and the light step clears the 2:1 contrast floor at 2.31:1, which
# the old thirteen-step per-grade ramp did not.
REPEATED_INK = "#1c5fae"
UNREPEATED_INK = "#74aee0"


def _fold(value: object) -> str:
    """Casefold and strip accents, so "Diaz-Rullo" matches "Díaz-Rullo"."""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(value))
        if unicodedata.category(c) != "Mn"
    ).lower()


@dataclass
class Panel:
    """One pyramid: counts per grade, and how many of each are unrepeated."""

    title: str
    subtitle: str
    counts: dict[str, int] = field(default_factory=dict)
    unrepeated: dict[str, int] = field(default_factory=dict)
    empty_note: str = ""

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def total_unrepeated(self) -> int:
        return sum(self.unrepeated.values())

    @property
    def widest(self) -> int:
        return max(self.counts.values(), default=0)

    @property
    def top_grade(self) -> str | None:
        return max(self.counts, key=french_ordinal, default=None)


def _tally(routes: pd.DataFrame) -> tuple[dict[str, int], dict[str, int]]:
    """Counts by grade, and the unrepeated subset, easiest grade first.

    "Unrepeated" is the site's ``num_ascents <= 1`` — the first ascent and
    nothing since. ``load_sport`` already folds that into ``status``, but the
    raw count is used here so a disputed route is still split on whether it was
    repeated rather than being lost to the more severe label.
    """
    counts = routes["grade_clean"].value_counts()
    unrep = routes[routes["num_ascents"] <= 1]["grade_clean"].value_counts()
    order = sorted(counts.index, key=french_ordinal)
    return ({g: int(counts[g]) for g in order},
            {g: int(unrep.get(g, 0)) for g in order})


def milestone_panels(sport: pd.DataFrame, floor: str = FLOOR) -> list[Panel]:
    """One panel per ``as_consensus`` milestone: the climber's prior FAs.

    The same selection notebook 03 already makes — that climber's first ascents
    at or above ``floor``, strictly before the breakthrough date — so the
    to-scale figure and the self-normalised one are drawn from identical rows
    and any difference between them is the scale, not the data.
    """
    cutoff = french_ordinal(floor)
    panels = []
    for _, m in breakthrough_table(sport, "as_consensus").iterrows():
        prior = sport[
            (sport["first_climber"] == m["climber"])
            & sport["first_ascent"].notna()
            & (sport["first_ascent"] < m["first_ascent"])
            & (sport["grade_order"] >= cutoff)
        ]
        counts, unrep = _tally(prior)
        panels.append(Panel(
            title=f"{m['grade']}  {m['route']}",
            subtitle=f"{m['climber']} · {m['first_ascent'].year}",
            counts=counts,
            unrepeated=unrep,
            empty_note=f"no prior first ascent\nof {floor} or harder recorded",
        ))
    return panels


def climber_panels(sport: pd.DataFrame, names: list[str] | None = None,
                   floor: str = FLOOR) -> list[Panel]:
    """One panel per named climber: every first ascent they have on record.

    A career-to-date pyramid, not a pyramid "as at" some event, so it is read
    against the scrape date rather than a breakthrough. Names are matched
    accent- and case-insensitively; a name with no first ascent in the dataset
    is kept as an empty panel rather than dropped, because a missing climber is
    worth seeing.
    """
    names = list(TODAYS_CLIMBERS if names is None else names)
    cutoff = french_ordinal(floor)
    folded = sport["first_climber"].map(_fold)

    panels = []
    for name in names:
        theirs = sport[(folded == _fold(name))
                       & (sport["grade_order"] >= cutoff)]
        counts, unrep = _tally(theirs)
        # the site's own spelling wins over the one asked for, so the panel
        # says "Jorge Díaz-Rullo" rather than the ASCII form used to find him
        spelled = (theirs["first_climber"].mode().iat[0] if len(theirs)
                   else name)
        years = theirs["first_ascent"].dt.year.dropna()
        span = (f"{int(years.min())}–{int(years.max())}" if len(years)
                else "no dated FA")
        panels.append(Panel(
            title=spelled,
            subtitle=f"{len(theirs)} first ascents · {span}",
            counts=counts,
            unrepeated=unrep,
            empty_note=f"no first ascent of\n{floor} or harder recorded",
        ))
    return panels


def shared_ladder(*panel_groups: list[Panel]) -> list[str]:
    """The grade axis every panel in every group shares, easiest first.

    Spanning all the groups at once is the point: it is what lets the milestone
    figure and the climber figure be laid beside each other, not just the panels
    within one of them.
    """
    seen = {g for panels in panel_groups for p in panels for g in p.counts}
    lo, hi = min(seen, key=french_ordinal), max(seen, key=french_ordinal)
    return FRENCH_SCALE[french_ordinal(lo):french_ordinal(hi) + 1]


def draw_pyramid_grid(panels: list[Panel], *, ladder: list[str], widest: int,
                      path, title: str, subtitle: str, ncols: int = 5,
                      tick: int = 10, panel_w: float = 3.55,
                      panel_h: float = 5.6):
    """Small multiples of ``panels``, every panel on the same two scales.

    ``ladder`` fixes the vertical (grade) scale and ``widest`` the horizontal
    (count) one; pass the same pair to two calls and the two figures are
    comparable to each other as well as internally. ``tick`` sets the faint
    vertical rules that act as a shared ruler across panels — without them a
    reader has to take the shared scale on trust.
    """
    nrows = -(-len(panels) // ncols)
    half = widest / 2
    # room to the right of the widest possible tier for its count label — the
    # widest tier is the one that needs it, so this is sized off `widest`, not
    # off whatever the busiest panel in this particular call happens to hold
    pad = max(half * 0.34, 3.0)
    # two rungs of headroom above the ladder for the panel's title block, so a
    # full top tier never has to share its row with the text
    head = 1.9
    fig, axes = plt.subplots(nrows, ncols, figsize=(panel_w * ncols,
                                                    panel_h * nrows),
                             dpi=120, facecolor=PAPER, squeeze=False)

    for ax, panel in zip(axes.ravel(), panels):
        ax.set_facecolor(PAPER)
        ax.set_xlim(-half - pad, half + pad)
        ax.set_ylim(-0.9, len(ladder) - 1 + head)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.set_xticks([])

        # the grade ladder, on every panel, so a tier's height is comparable
        ax.set_yticks(range(len(ladder)))
        ax.set_yticklabels(ladder, fontsize=8.5, color=MUTED)
        ax.tick_params(axis="y", length=0, pad=2)

        # the shared ruler: faint rules at +/- `tick` routes
        for t in range(tick, int(half) + 1, tick):
            for x in (-t, t):
                ax.axvline(x, color=GRID, lw=.8, zorder=0)
        ax.axvline(0, color=GRID, lw=.8, zorder=0)

        ax.text(-half - pad, len(ladder) - 1 + head, panel.title,
                fontsize=12, color=INK, ha="left", va="top")
        ax.text(-half - pad, len(ladder) - 1 + head - 0.62, panel.subtitle,
                fontsize=9.5, color=MUTED, ha="left", va="top")

        if not panel.counts:
            ax.text(0, (len(ladder) - 1) / 2, panel.empty_note, fontsize=10,
                    color=MUTED, ha="center", va="center", linespacing=1.6,
                    style="italic")
            continue

        for grade, n in panel.counts.items():
            y = ladder.index(grade)
            u = panel.unrepeated.get(grade, 0)
            r = n - u
            # centred tier: the repeated core, then the unrepeated wings, with
            # a 2px paper gap between them rather than a stroke. A tier that is
            # wholly one or the other degrades to a single block.
            gap = 0.06 if r and u else 0.0
            if r:
                ax.add_patch(Rectangle((-r / 2, y - 0.34), r, 0.68,
                                       facecolor=REPEATED_INK, lw=0, zorder=2))
            if u:
                for x0 in (-n / 2, r / 2 + gap):
                    ax.add_patch(Rectangle((x0, y - 0.34), u / 2 - gap, 0.68,
                                           facecolor=UNREPEATED_INK, lw=0,
                                           zorder=2))
            label = f"{n}" if not u else f"{n}  ({u} unrep.)"
            ax.text(n / 2 + half * 0.035, y, label, fontsize=8.5, color=MUTED,
                    ha="left", va="center")

        ax.text(-half - pad, -0.75,
                f"{panel.total} FAs · {panel.total_unrepeated} unrepeated · "
                f"top {panel.top_grade}", fontsize=8.5, color=MUTED,
                ha="left", va="center")

    for ax in axes.ravel()[len(panels):]:
        ax.axis("off")

    # legend, drawn once: identity never rests on colour alone anyway, since
    # the count label spells the unrepeated share out beside every tier
    handles = [Rectangle((0, 0), 1, 1, facecolor=c, lw=0)
               for c in (REPEATED_INK, UNREPEATED_INK)]
    fig.legend(handles, ["repeated by someone else", "unrepeated"],
               loc="upper right", bbox_to_anchor=(.995, .995), frameon=False,
               fontsize=9.5, labelcolor=MUTED, ncol=2, handlelength=1.1,
               handleheight=1.1, columnspacing=1.4)

    fig.suptitle(title, color=INK, fontsize=15, x=.008, ha="left", y=.995)
    fig.text(.008, .968, subtitle, fontsize=9.5, color=MUTED, va="top")
    plt.tight_layout(rect=(0, 0, 1, .952))
    fig.savefig(path, facecolor=PAPER, bbox_inches="tight")
    return fig


def panels_frame(panels: list[Panel], kind: str) -> pd.DataFrame:
    """The panels as a table, for the CSV beside the figure."""
    return pd.DataFrame([{
        "kind": kind,
        "panel": p.title,
        "subtitle": p.subtitle,
        "n_fas": p.total,
        "n_unrepeated": p.total_unrepeated,
        "top_grade": p.top_grade,
        "widest_tier": p.widest,
        "pyramid": "  ".join(f"{g}x{n}" for g, n in p.counts.items()) or "-",
    } for p in panels])


def build() -> None:
    sport = load_sport()
    milestones = milestone_panels(sport)
    climbers = climber_panels(sport)

    # one ladder and one count scale across both figures, so the two are
    # comparable to each other and not only panel-to-panel within each
    ladder = shared_ladder(milestones, climbers)
    widest = max(p.widest for p in milestones + climbers)
    print(f"shared ladder {ladder[0]}–{ladder[-1]} ({len(ladder)} rungs), "
          f"shared scale to {widest}")

    draw_pyramid_grid(
        milestones, ladder=ladder, widest=widest, ncols=5,
        path=config.FIGURES_DIR / "milestone_pyramids_to_scale.png",
        title="The milestone pyramids, all on one scale",
        subtitle="prior first ascents at the moment of the breakthrough · "
                 "every panel shares the grade ladder and the count scale · "
                 "faint rules every 10 routes")
    draw_pyramid_grid(
        climbers, ladder=ladder, widest=widest, ncols=4,
        path=config.FIGURES_DIR / "todays_climbers_pyramids.png",
        title="Today's hardest first ascentionists, on the same scale",
        subtitle="every recorded first ascent of 7c and up, to the 2026-09-09 "
                 "scrape · same grade ladder and count scale as the milestone "
                 "figure")

    frame = pd.concat([panels_frame(milestones, "milestone"),
                       panels_frame(climbers, "climber")], ignore_index=True)
    frame.to_csv(config.PROCESSED_DIR / "pyramids_to_scale.csv", index=False)
    print(frame.drop(columns=["subtitle"]).to_string(index=False))


def main() -> None:
    build()


if __name__ == "__main__":
    main()
