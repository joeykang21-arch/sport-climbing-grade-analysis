"""Scraping, cleaning and analysis of climbing-history.org sport ascent data.

The package is organised as a small pipeline:

    scrape_index    -> data/raw/climbs_index.csv
    scrape_details  -> data/raw/climbs_detail.csv
    clean           -> data/processed/climbs_detail.csv
    build_datasets  -> data/processed/sport_routes*.csv, boulders.csv
"""

__version__ = "1.0.0"

__all__ = ["config", "grades", "clean", "runlog", "build_datasets"]
