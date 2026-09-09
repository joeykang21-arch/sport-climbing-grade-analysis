"""Scrape the paginated climbs listing of climbing-history.org.

Walks ``/climbs?page=1`` onward and writes one row per listed climb to
``data/raw/climbs_index.csv``. The listing carries the editorial notes and
exclusion reasons that the individual climb pages do not, which is why it is
collected separately from :mod:`sportgradehistory.scrape_details`.

Every climb type is collected, not just sport: the boulder rows are the control
group for the sport analysis, and both come out of the same snapshot.

The run is single-threaded, sleeps 1s between pages, appends each page to
``climbs_index.partial.csv`` and checkpoints after every one, so an interrupted
run resumes where it stopped instead of starting over.

Run as::

    python -m sportgradehistory.scrape_index
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import config
from .runlog import Checkpoint, Progress, setup_logging, update_manifest, utc_now

LISTING_URL = config.SITE_ROOT + "/climbs"

COLUMNS = [
    "climb_name",
    "climb_url",
    "type",
    "grade",
    "ascents_recorded",
    "notes",
    "exclude_reason",
    "page",
]

# Safety cap only. The run normally ends by hitting STOP_AFTER_EMPTY empty pages;
# the listing was 365 pages when the boulder repo scraped it and is past 400 now,
# so a hardcoded end is exactly how a scrape silently truncates.
DEFAULT_END_PAGE = 600
STOP_AFTER_EMPTY = 3


def fetch_listing(session: requests.Session, page: int, timeout: int = 15, logger=None):
    """Fetch one listing page, or ``None`` if the request fails."""
    try:
        response = session.get(
            LISTING_URL,
            params={"page": page},
            headers=config.DEFAULT_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as exc:
        if logger:
            logger.warning("page %s: %s", page, exc)
        return None


def parse_listing(soup: BeautifulSoup, page: int) -> list[dict[str, Any]]:
    """Parse the climbs table on one listing page into a list of rows."""
    table = soup.find("table")
    if table is None:
        return []

    rows: list[dict[str, Any]] = []
    body = table.find("tbody") or table

    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue  # header or malformed row

        link = cells[0].find("a")
        name = (link or cells[0]).get_text(strip=True)
        href = link["href"] if link and link.get("href") else ""
        if href and not href.startswith("http"):
            href = config.SITE_ROOT + href

        rows.append(
            {
                "climb_name": name,
                "climb_url": href,
                "type": cells[1].get_text(strip=True),
                "grade": cells[2].get_text(strip=True),
                "ascents_recorded": cells[3].get_text(strip=True),
                "notes": _parse_notes(cells[4]),
                "exclude_reason": (
                    cells[5].get_text(strip=True) if len(cells) > 5 else ""
                ),
                "page": page,
            }
        )

    return rows


def _parse_notes(cell) -> str:
    """Extract the note text from a listing cell, dropping the references block."""
    paragraph = cell.find("p")
    if paragraph:
        return paragraph.get_text(" ", strip=True)

    text = cell.get_text(" ", strip=True)
    index = text.find("References")
    return text[:index].strip() if index != -1 else text


def _append_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append rows to the partial CSV, writing the header if the file is new."""
    if not rows:
        return
    is_new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def scrape(
    start_page: int = 1,
    end_page: int = DEFAULT_END_PAGE,
    delay: float = 1.0,
    resume: bool = True,
) -> pd.DataFrame:
    """Scrape the listing from ``start_page`` until it runs out of pages."""
    logger = setup_logging("scrape_index")
    checkpoint = Checkpoint(config.CHECKPOINT_INDEX, "index")

    if not resume:
        config.PARTIAL_INDEX_CSV.unlink(missing_ok=True)
        checkpoint.discard()
        checkpoint = Checkpoint(config.CHECKPOINT_INDEX, "index")

    first_page = checkpoint.resume_from(start_page)
    retry = [p for p in checkpoint.errored if p < first_page]

    started = utc_now()
    logger.info(
        "index scrape starting: pages %s-%s, delay %ss, resuming at %s, %s to retry",
        start_page, end_page, delay, first_page, len(retry),
    )
    if first_page > start_page:
        print(f"resuming from page {first_page} ({len(retry)} earlier failures to retry)")

    counts = dict(checkpoint.data.get("counts") or {"rows": 0, "pages": 0, "errors": 0})
    counts.setdefault("rows", 0)
    counts.setdefault("pages", 0)
    counts.setdefault("errors", 0)

    progress = Progress(total=end_page - first_page + 1, every=100, unit="pages")
    consecutive_empty = 0
    last_page_seen = first_page - 1

    with requests.Session() as session:
        for page in retry + list(range(first_page, end_page + 1)):
            soup = fetch_listing(session, page, logger=logger)

            if soup is None:
                counts["errors"] += 1
                checkpoint.mark_errored(page)
                checkpoint.flush()
                logger.warning("page %s: fetch failed, will retry on resume", page)
                time.sleep(delay * 3)  # back off before trying the next page
                progress.tick()
                continue

            rows = parse_listing(soup, page)
            _append_rows(config.PARTIAL_INDEX_CSV, rows)
            checkpoint.clear_errored(page)

            counts["rows"] += len(rows)
            counts["pages"] += 1
            logger.info("page %s: %s rows", page, len(rows))

            if page >= first_page:
                last_page_seen = page
                checkpoint.mark_done(page, counts)

            if rows:
                consecutive_empty = 0
            else:
                consecutive_empty += 1
                if consecutive_empty >= STOP_AFTER_EMPTY:
                    logger.info(
                        "page %s: %s consecutive empty pages, end of listing",
                        page, consecutive_empty,
                    )
                    break

            time.sleep(delay)
            progress.tick()

    progress.report()

    frame = _finalise(logger)
    update_manifest(
        "index",
        {
            "source": LISTING_URL,
            "started_utc": checkpoint.data.get("started_utc", started),
            "finished_utc": utc_now(),
            "elapsed": progress.elapsed(),
            "rows": int(len(frame)),
            "first_page": start_page,
            "last_page": last_page_seen,
            "pages_fetched": counts["pages"],
            "fetch_errors": counts["errors"],
            "unrecovered_pages": checkpoint.errored,
            "delay_seconds": delay,
            "output": str(config.RAW_INDEX_CSV.relative_to(config.ROOT).as_posix()),
        },
    )

    if not checkpoint.errored:
        checkpoint.discard()
        config.PARTIAL_INDEX_CSV.unlink(missing_ok=True)
    else:
        logger.warning("leaving resume state in place: %s pages still failing",
                       len(checkpoint.errored))

    return frame


def _finalise(logger) -> pd.DataFrame:
    """Assemble the partial file into the final CSV, deduplicated and in order."""
    if not config.PARTIAL_INDEX_CSV.exists():
        logger.error("no partial file to finalise")
        return pd.DataFrame(columns=COLUMNS)

    frame = pd.read_csv(config.PARTIAL_INDEX_CSV, encoding="utf-8")
    before = len(frame)
    # A page refetched after an interrupted run appends its rows twice; identical
    # duplicates are that, not real repeats in the listing.
    frame = frame.drop_duplicates()
    frame = frame.sort_values("page", kind="stable").reset_index(drop=True)

    config.RAW_INDEX_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(config.RAW_INDEX_CSV, index=False, encoding="utf-8")

    logger.info("wrote %s: %s rows (%s duplicates dropped)",
                config.RAW_INDEX_CSV, len(frame), before - len(frame))
    print(f"collected {len(frame):,} listed climbs -> {config.RAW_INDEX_CSV}")
    return frame


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Scrape the climbing-history.org climbs listing."
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument(
        "--end-page", type=int, default=DEFAULT_END_PAGE,
        help="safety cap; the run normally stops when the listing runs out",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument(
        "--no-resume", action="store_true",
        help="discard any checkpoint and scrape the range from the start",
    )
    args = parser.parse_args(argv)

    config.ensure_dirs()
    scrape(args.start_page, args.end_page, args.delay, resume=not args.no_resume)


if __name__ == "__main__":
    main()
