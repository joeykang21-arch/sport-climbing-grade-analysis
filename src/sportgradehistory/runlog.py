"""Run plumbing shared by the two scrapers: logging, resume state, manifest.

A full detail scrape is upwards of two hours of sequential requests, so a
dropped connection part-way through must not cost the whole run. Three pieces
make that survivable:

* :func:`setup_logging` sends the verbose per-page record to ``data/raw/scrape.log``
  and nothing to stdout.
* :class:`Progress` is the only thing that prints, once every 100 pages.
* :class:`Checkpoint` persists where the run got to, flushed after every page,
  next to a ``.partial.csv`` holding the rows collected so far.

:func:`update_manifest` records what a finished run produced, so the committed
snapshot says when it was taken and by which revision of the code.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config


def utc_now() -> str:
    """The current UTC time as an ISO-8601 string, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def setup_logging(name: str, path: Path | None = None) -> logging.Logger:
    """Return a logger that appends to ``data/raw/scrape.log`` and stays off stdout.

    Appending rather than truncating is deliberate: a resumed run is part of the
    same scrape as the one it continues, and the log is the only record of what
    the earlier attempt already fetched.
    """
    path = path or config.SCRAPE_LOG
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"sportgradehistory.{name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # keep it out of the root logger's stdout handler

    if not logger.handlers:
        handler = logging.FileHandler(path, mode="a", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
        )
        logger.addHandler(handler)

    return logger


class Progress:
    """Print one stdout line every ``every`` items, and nothing in between.

    The brief for these scrapers is a verbose file log and a quiet terminal, so
    this is the only thing either scraper writes to stdout.
    """

    def __init__(self, total: int, every: int = 100, unit: str = "pages") -> None:
        self.total = total
        self.every = every
        self.unit = unit
        self.done = 0
        self.started = time.monotonic()

    def tick(self, n: int = 1) -> None:
        """Count ``n`` more items, printing if that crosses a reporting boundary."""
        previous = self.done
        self.done += n
        if self.done // self.every > previous // self.every:
            self.report()

    def report(self) -> None:
        """Print the progress line unconditionally."""
        remaining = max(self.total - self.done, 0)
        print(
            f"{self.unit} done: {self.done:>6,} | "
            f"remaining: {remaining:>6,} | "
            f"elapsed: {self.elapsed()}",
            flush=True,
        )

    def elapsed(self) -> str:
        """Wall time since the run started, as ``H:MM:SS``."""
        seconds = int(time.monotonic() - self.started)
        return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    @property
    def seconds(self) -> float:
        return time.monotonic() - self.started


class Checkpoint:
    """Resume state for one scraper, rewritten after every page.

    Both scrapers walk a contiguous range in order, so "how far did we get" is a
    single integer rather than a set of every id visited. That keeps the file
    tiny and the flush cheap enough to do on every single page -- which is the
    point, since anything less loses work on a crash. Pages that errored are
    listed separately and retried first on resume, so a transient failure
    mid-range is not silently skipped.
    """

    def __init__(self, path: Path, scraper: str) -> None:
        self.path = path
        self.scraper = scraper
        self.data: dict[str, Any] = {
            "scraper": scraper,
            "started_utc": utc_now(),
            "updated_utc": None,
            "last_completed": None,
            "errored": [],
            "counts": {},
        }
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                # A checkpoint torn by a crash mid-write is not worth failing
                # over; the partial CSV still holds the rows, and starting the
                # range again only costs time.
                pass

    @property
    def last_completed(self) -> int | None:
        return self.data.get("last_completed")

    @property
    def errored(self) -> list[int]:
        return list(self.data.get("errored", []))

    def resume_from(self, default: int) -> int:
        """The first item to fetch: one past the last completed, or ``default``."""
        last = self.last_completed
        return default if last is None else max(default, last + 1)

    def mark_done(self, item: int, counts: dict[str, int]) -> None:
        self.data["last_completed"] = item
        self.data["counts"] = counts
        self.flush()

    def mark_errored(self, item: int) -> None:
        errored = self.data.setdefault("errored", [])
        if item not in errored:
            errored.append(item)

    def clear_errored(self, item: int) -> None:
        errored = self.data.setdefault("errored", [])
        if item in errored:
            errored.remove(item)

    def flush(self) -> None:
        self.data["updated_utc"] = utc_now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def discard(self) -> None:
        """Remove the checkpoint once the run has finished cleanly."""
        self.path.unlink(missing_ok=True)


def git_commit() -> str | None:
    """The repo's current commit, so the manifest says which code scraped this."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=config.ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def update_manifest(section: str, payload: dict[str, Any]) -> None:
    """Merge ``payload`` into ``data/raw/scrape_manifest.json`` under ``section``.

    The two scrapers run separately and each own one section, so the manifest is
    read-modify-written rather than overwritten.
    """
    manifest: dict[str, Any] = {}
    if config.SCRAPE_MANIFEST.exists():
        try:
            manifest = json.loads(config.SCRAPE_MANIFEST.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}

    manifest[section] = {**payload, "git_commit": git_commit()}
    manifest["updated_utc"] = utc_now()

    config.SCRAPE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    config.SCRAPE_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
