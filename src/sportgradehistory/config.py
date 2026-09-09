"""Shared paths and constants.

Every path is derived from the repository root so scripts and notebooks
resolve the same files regardless of the working directory they run from.
"""

from pathlib import Path

# src/sportgradehistory/config.py -> src/sportgradehistory -> src -> repo root
ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
ARCHIVE_DIR = RAW_DIR / "archive"
PROCESSED_DIR = DATA_DIR / "processed"
FIGURES_DIR = ROOT / "figures"

# ── Raw scrape output ─────────────────────────────────────────────────────────
RAW_INDEX_CSV = RAW_DIR / "climbs_index.csv"
RAW_DETAIL_CSV = RAW_DIR / "climbs_detail.csv"

# Resume state, written while a scrape is in flight and removed when it
# finishes. Both are gitignored: only the completed snapshot is committed.
PARTIAL_INDEX_CSV = RAW_DIR / "climbs_index.partial.csv"
PARTIAL_DETAIL_CSV = RAW_DIR / "climbs_detail.partial.csv"
CHECKPOINT_INDEX = RAW_DIR / ".checkpoint_index.json"
CHECKPOINT_DETAIL = RAW_DIR / ".checkpoint_details.json"

SCRAPE_LOG = RAW_DIR / "scrape.log"
SCRAPE_MANIFEST = RAW_DIR / "scrape_manifest.json"

# ── The previous snapshot, kept for diffing only ──────────────────────────────
# Never an input to the pipeline. See data/raw/archive/README.md.
ARCHIVE_INDEX_CSV = ARCHIVE_DIR / "climbs_index.csv"
ARCHIVE_DETAIL_CSV = ARCHIVE_DIR / "climbs_detail.csv"

# ── Cleaned / derived datasets ────────────────────────────────────────────────
CLEAN_DETAIL_CSV = PROCESSED_DIR / "climbs_detail.csv"
CLEAN_INDEX_CSV = PROCESSED_DIR / "climbs_index.csv"
SPORT_CSV = PROCESSED_DIR / "sport_routes.csv"
SPORT_8A_PLUS_CSV = PROCESSED_DIR / "sport_8a_and_above.csv"
REGRADED_ROUTES_CSV = PROCESSED_DIR / "regraded_routes.csv"
BOULDERS_CSV = PROCESSED_DIR / "boulders.csv"
# Written by the milestone analysis, not by build_datasets: sport's
# claimed-but-unconfirmed ascents, with a status column.
DISPUTED_ASCENTS_CSV = PROCESSED_DIR / "disputed_ascents.csv"

SITE_ROOT = "https://climbing-history.org"

# Sent on every request so the site's operator can tell who we are and why.
USER_AGENT = "Mozilla/5.0 (compatible; sport-grade-history/1.0)"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}


def ensure_dirs() -> None:
    """Create the data and figure directories if they do not exist yet."""
    for path in (RAW_DIR, ARCHIVE_DIR, PROCESSED_DIR, FIGURES_DIR):
        path.mkdir(parents=True, exist_ok=True)
