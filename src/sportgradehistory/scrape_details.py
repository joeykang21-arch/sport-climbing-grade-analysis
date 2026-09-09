"""Scrape the individual climb pages of climbing-history.org.

Walks ``/climb/1`` upward, keeps every page that records at least one successful
ascent, and writes one row per climb to ``data/raw/climbs_detail.csv``. Every
climb type is collected, not just sport: the boulder rows are the control group
for the sport analysis, and both come out of the same snapshot.

The run is single-threaded, sleeps 0.5s per page, appends each kept row to
``climbs_detail.partial.csv`` and checkpoints after every page, so an
interrupted run resumes where it stopped. Expect two to three hours.

Run as::

    python -m sportgradehistory.scrape_details

Four things about the live page structure differ from what the boulder repo's
scraper assumed, and are handled here. See PLAN.md 0.2-0.5 for the evidence.

1. The ascent count now reads ``"3 successful ascents and 1 unsuccessful
   attempt recorded"``, so a pattern requiring ``"ascents recorded"`` matches
   nothing and every climb parses as zero ascents.
2. The ascents table gained a blank leading column, so reading its cells by
   fixed position is off by one. Cells are located by header name instead.
3. Unsuccessful attempts share that table, marked ``class="dnf"``. They are not
   ascents and must not be read as the first one.
4. The ``<h1>`` dropdown gained a ``Notes Log`` tab. Removing the whole
   dropdown, rather than matching known tab labels, is what keeps the nav text
   out of ``location``.
"""

from __future__ import annotations

import argparse
import copy
import csv
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import config
from .clean import split_type_and_location
from .runlog import Checkpoint, Progress, setup_logging, update_manifest, utc_now

CLIMB_URL = config.SITE_ROOT + "/climb/{}"

# Safety cap only. The run normally ends after STOP_AFTER_MISSING consecutive
# 404s. The boulder repo hardcoded 7512; id 8361 exists today, so a fixed end is
# how a scrape silently truncates.
DEFAULT_END_ID = 9000
STOP_AFTER_MISSING = 150

# Tab labels rendered inside the <h1>. The dropdown is removed wholesale, which
# covers every tab including ones added later; this set is the fallback for any
# nav link rendered outside it.
NAV_LABELS = {"more", "change log", "notes log", "threads", "ascents", "info"}

# Fix 1: "N successful ascents" is now followed by the unsuccessful-attempt
# count before the word "recorded", so the match stops at the noun.
_ASCENT_COUNT = re.compile(r"(\d[\d,]*)\s+successful\s+ascents?\b", re.IGNORECASE)
_TRAILING_BADGE = re.compile(r"\s*\d+\s*$")
# Styles the site records for an attempt that did not succeed.
_NOT_SENT = re.compile(r"did not", re.IGNORECASE)

# Ascents table header -> the column it populates for the first ascent.
ASCENT_FIELDS = {
    "climber": "first_climber",
    "style": "first_style",
    "ascent date": "first_ascent_date",
    "suggested grade": "first_suggested_grade",
}

COLUMNS = [
    "climb_id",
    "climb_url",
    "climb_name",
    "grade",
    "climb_type",
    "location",
    "num_ascents",
    "first_climber",
    "first_style",
    "first_ascent_date",
    "first_suggested_grade",
]


def _heading_text(h1) -> str:
    """Return the ``<h1>`` text with its navigation dropdown removed.

    The site renders the More / Change Log / Notes Log / Threads dropdown inside
    the heading, so ``get_text()`` on the whole element appends the tab labels
    to the location. That is the original cause of the corrupted ``climb_type``
    and ``location`` columns in ``data/raw/archive/``.

    The whole ``div.dropdown`` goes rather than a list of known labels: the
    boulder repo matched labels, the site later added a ``Notes Log`` tab, and
    the defect came straight back. Removing the container is not sensitive to
    which tabs exist. The label matching is kept as a fallback for any nav link
    rendered outside the dropdown.
    """
    heading = copy.copy(h1)

    for dropdown in heading.find_all("div", class_="dropdown"):
        dropdown.decompose()

    for link in heading.find_all("a"):
        # Tab links can carry a badge count, e.g. "Threads 2".
        label = _TRAILING_BADGE.sub("", link.get_text(" ", strip=True).lower()).strip()
        if label in NAV_LABELS:
            link.decompose()

    return heading.get_text(" ", strip=True)


def parse_header(soup: BeautifulSoup) -> dict[str, str | None]:
    """Parse the page heading into name, grade, type and location.

    The heading reads ``"<name> | <grade> <type> <preposition> <location>"``,
    where the preposition is ``at``, ``in`` or ``on`` depending on the crag.
    Ungraded alpine routes omit both the grade and the type, which is what
    produces the column shift ``clean.clean_detail_frame`` repairs.
    """
    result: dict[str, str | None] = {
        "climb_name": None,
        "grade": None,
        "climb_type": None,
        "location": None,
    }

    h1 = soup.find("h1")
    if not h1:
        return result

    text = _heading_text(h1)

    name, _, rest = text.partition(" | ")
    result["climb_name"] = name.strip() or None
    rest = rest.strip()
    if not rest:
        return result

    # The grade is the first token; the remainder is "<type> <preposition> <location>".
    grade, _, type_and_location = rest.partition(" ")
    climb_type, location = split_type_and_location(type_and_location, None)

    if climb_type is None:
        # No recognisable type means the heading had no grade either, and what
        # was split off is really the whole location (e.g. "Mt. Everest").
        result["location"] = rest
        return result

    result["grade"] = grade.strip() or None
    result["climb_type"] = climb_type
    result["location"] = location
    return result


def _ascents_table(soup: BeautifulSoup):
    """Find the ascents table and its lower-cased header names."""
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        if "climber" in headers and "ascent date" in headers:
            return table, headers
    return None, []


def _first_successful_row(table, n_columns: int):
    """Return the cells of the first row that records a successful ascent.

    Three kinds of row share this table and only one of them is an ascent:

    * the ascent itself, one cell per header;
    * its subtitle and detail rows, which span the table with ``colspan`` and
      hold the "First ascent." note, the story and the references;
    * unsuccessful attempts, marked ``class="dnf"``, whose style reads
      "Lead | did not finish".

    Filtering on shape and on the ``dnf`` marker rather than on the site's
    layout classes keeps this working if the rows are restyled.
    """
    body = table.find("tbody") or table

    for tr in body.find_all("tr"):
        classes = tr.get("class") or []
        if "dnf" in classes:
            continue

        cells = tr.find_all("td")
        if not cells:
            continue
        if any(cell.get("colspan") for cell in cells):
            continue  # a subtitle or detail row, not an ascent
        if len(cells) < n_columns - 1:
            continue

        # Belt and braces: a failed attempt whose row is not classed "dnf" is
        # still identifiable from its style text.
        if any(_NOT_SENT.search(cell.get_text(" ", strip=True)) for cell in cells):
            continue

        return cells

    return None


def parse_ascents(soup: BeautifulSoup, logger=None) -> dict[str, Any]:
    """Parse the ascent count and the first recorded successful ascent."""
    result: dict[str, Any] = {
        "num_ascents": 0,
        "first_climber": None,
        "first_style": None,
        "first_ascent_date": None,
        "first_suggested_grade": None,
    }

    match = _ASCENT_COUNT.search(soup.get_text(" ", strip=True))
    if not match:
        return result
    result["num_ascents"] = int(match.group(1).replace(",", ""))
    if result["num_ascents"] == 0:
        return result

    table, headers = _ascents_table(soup)
    if table is None:
        return _parse_ascents_without_table(soup, result)

    cells = _first_successful_row(table, len(headers))
    if cells is None:
        if logger:
            logger.warning("ascents table has no successful-ascent row")
        return result

    # Cells are located by header name, not by position: the table gained a
    # blank leading column at some point and every fixed index shifted by one.
    index = {name: i for i, name in enumerate(headers)}
    for header, field in ASCENT_FIELDS.items():
        position = index.get(header)
        if position is None or position >= len(cells):
            continue
        cell = cells[position]
        link = cell.find("a") if field == "first_climber" else None
        text = (link or cell).get_text(" ", strip=True)
        result[field] = text or None

    return result


def _parse_ascents_without_table(
    soup: BeautifulSoup, result: dict[str, Any]
) -> dict[str, Any]:
    """Fallback for pages that render ascents as rows of divs instead of a table."""
    heading = soup.find(
        lambda tag: tag.name in ("h2", "h3", "h4") and "Ascent" in tag.get_text()
    )
    if heading is None:
        return result

    section = heading.find_next_sibling()
    for _ in range(20):  # bounded walk: give up rather than scan the whole page
        if section is None:
            break
        text = section.get_text(" ", strip=True)
        link = section.find("a")
        if link and re.search(r"\d{4}", text):  # a year means this is an ascent row
            result["first_climber"] = link.get_text(strip=True) or None
            date = re.search(
                r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}|Before \S+ \d{4}|\d{4})", text
            )
            result["first_ascent_date"] = date.group(1) if date else None
            break
        section = section.find_next_sibling()

    return result


def fetch_climb(session: requests.Session, climb_id: int, timeout: int = 15, logger=None):
    """Fetch one climb page. Returns ``(soup, status)``; soup is ``None`` on failure."""
    url = CLIMB_URL.format(climb_id)
    try:
        response = session.get(url, headers=config.DEFAULT_HEADERS, timeout=timeout)
        if response.status_code == 404:
            return None, 404
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser"), response.status_code
    except requests.RequestException as exc:
        if logger:
            logger.warning("climb %s: %s", climb_id, exc)
        return None, None


def _append_row(path: Path, row: dict[str, Any]) -> None:
    """Append one row to the partial CSV, writing the header if the file is new."""
    is_new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def scrape(
    start_id: int = 1,
    end_id: int = DEFAULT_END_ID,
    delay: float = 0.5,
    resume: bool = True,
) -> pd.DataFrame:
    """Scrape climb pages from ``start_id`` until the ids run out."""
    logger = setup_logging("scrape_details")
    checkpoint = Checkpoint(config.CHECKPOINT_DETAIL, "details")

    if not resume:
        config.PARTIAL_DETAIL_CSV.unlink(missing_ok=True)
        checkpoint.discard()
        checkpoint = Checkpoint(config.CHECKPOINT_DETAIL, "details")

    first_id = checkpoint.resume_from(start_id)
    retry = [i for i in checkpoint.errored if i < first_id]

    started = utc_now()
    logger.info(
        "detail scrape starting: ids %s-%s, delay %ss, resuming at %s, %s to retry",
        start_id, end_id, delay, first_id, len(retry),
    )
    if first_id > start_id:
        print(f"resuming from climb {first_id} ({len(retry)} earlier failures to retry)")

    counts = dict(checkpoint.data.get("counts") or {})
    for key in ("kept", "no_ascents", "missing", "errors"):
        counts.setdefault(key, 0)

    progress = Progress(total=end_id - first_id + 1, every=100, unit="pages")
    consecutive_missing = 0
    seen_any_hit = counts["kept"] > 0
    last_id_seen = first_id - 1

    with requests.Session() as session:
        for climb_id in retry + list(range(first_id, end_id + 1)):
            soup, status = fetch_climb(session, climb_id, logger=logger)

            if status == 404:
                counts["missing"] += 1
                consecutive_missing += 1
                checkpoint.clear_errored(climb_id)
                logger.debug("climb %s: 404", climb_id)
                if climb_id >= first_id:
                    last_id_seen = climb_id
                    checkpoint.mark_done(climb_id, counts)
                # Ids are handed out sequentially, so a long unbroken run of
                # 404s means the top of the range -- but only once the scrape
                # has actually found something, since the low ids include gaps.
                if seen_any_hit and consecutive_missing >= STOP_AFTER_MISSING:
                    logger.info(
                        "climb %s: %s consecutive 404s, end of range",
                        climb_id, consecutive_missing,
                    )
                    break
                time.sleep(delay)
                progress.tick()
                continue

            if soup is None:
                counts["errors"] += 1
                checkpoint.mark_errored(climb_id)
                checkpoint.flush()
                logger.warning("climb %s: fetch failed, will retry on resume", climb_id)
                time.sleep(delay * 3)  # back off before trying the next page
                progress.tick()
                continue

            consecutive_missing = 0
            seen_any_hit = True
            checkpoint.clear_errored(climb_id)

            ascents = parse_ascents(soup, logger=logger)
            if ascents["num_ascents"] == 0:
                counts["no_ascents"] += 1
                logger.debug("climb %s: no recorded ascents, skipped", climb_id)
            else:
                header = parse_header(soup)
                _append_row(
                    config.PARTIAL_DETAIL_CSV,
                    {
                        "climb_id": climb_id,
                        "climb_url": CLIMB_URL.format(climb_id),
                        **header,
                        **ascents,
                    },
                )
                counts["kept"] += 1
                logger.info(
                    "climb %s: %r %s %s, %s ascents",
                    climb_id, header["climb_name"], header["grade"],
                    header["climb_type"], ascents["num_ascents"],
                )

            if climb_id >= first_id:
                last_id_seen = climb_id
                checkpoint.mark_done(climb_id, counts)

            time.sleep(delay)
            progress.tick()

    progress.report()

    frame = _finalise(logger)
    update_manifest(
        "details",
        {
            "source": CLIMB_URL.format("<id>"),
            "started_utc": checkpoint.data.get("started_utc", started),
            "finished_utc": utc_now(),
            "elapsed": progress.elapsed(),
            "rows": int(len(frame)),
            "first_id": start_id,
            "last_id": last_id_seen,
            "kept_with_ascents": counts["kept"],
            "skipped_no_ascents": counts["no_ascents"],
            "missing_404": counts["missing"],
            "fetch_errors": counts["errors"],
            "unrecovered_ids": checkpoint.errored,
            "delay_seconds": delay,
            "output": str(config.RAW_DETAIL_CSV.relative_to(config.ROOT).as_posix()),
        },
    )

    if not checkpoint.errored:
        checkpoint.discard()
        config.PARTIAL_DETAIL_CSV.unlink(missing_ok=True)
    else:
        logger.warning("leaving resume state in place: %s ids still failing",
                       len(checkpoint.errored))

    return frame


def _finalise(logger) -> pd.DataFrame:
    """Assemble the partial file into the final CSV, deduplicated and in id order."""
    if not config.PARTIAL_DETAIL_CSV.exists():
        logger.error("no partial file to finalise")
        return pd.DataFrame(columns=COLUMNS)

    frame = pd.read_csv(config.PARTIAL_DETAIL_CSV, encoding="utf-8")
    before = len(frame)
    # An id refetched after an interrupted run appends twice; the later read is
    # the one to keep.
    frame = frame.drop_duplicates(subset=["climb_id"], keep="last")
    frame = frame.sort_values("climb_id", kind="stable").reset_index(drop=True)

    config.RAW_DETAIL_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(config.RAW_DETAIL_CSV, index=False, encoding="utf-8")

    logger.info("wrote %s: %s rows (%s duplicates dropped)",
                config.RAW_DETAIL_CSV, len(frame), before - len(frame))
    print(f"collected {len(frame):,} climbs with ascents -> {config.RAW_DETAIL_CSV}")
    return frame


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Scrape climbing-history.org climb pages."
    )
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument(
        "--end-id", type=int, default=DEFAULT_END_ID,
        help="safety cap; the run normally stops when the ids run out",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    parser.add_argument(
        "--no-resume", action="store_true",
        help="discard any checkpoint and scrape the range from the start",
    )
    args = parser.parse_args(argv)

    config.ensure_dirs()
    scrape(args.start_id, args.end_id, args.delay, resume=not args.no_resume)


if __name__ == "__main__":
    main()
