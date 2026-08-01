"""Fetch retracted works from the OpenAlex API and save them as compact JSON.

Queries the OpenAlex `/works` endpoint for records where `is_retracted` is
true, walks through all pages using cursor-based pagination, and extracts a
minimal set of fields (DOI, title, primary topic, host venue/publisher, and
publication year) for each work. Results are written to
`data/retractions.json` as a single-line, whitespace-free JSON array to keep
the file size as small as possible.

Usage:
    python scripts/fetch_retractions.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import requests

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "retractions.json"
PER_PAGE = 200
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 2
REQUEST_TIMEOUT = 30

# OpenAlex "polite pool" — supplying a contact email gets faster, more
# reliable responses. Update this to a real contact address if desired.
MAILTO = "example@example.com"

FIELDS = "id,doi,title,primary_topic,primary_location,publication_year"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).resolve().parent / "fetch_retractions.log"),
    ],
)
logger = logging.getLogger("fetch_retractions")


def fetch_page(cursor: str, session: requests.Session) -> dict[str, Any]:
    """Fetch a single page of retracted works for the given cursor.

    Retries with exponential backoff on network errors or non-2xx responses.
    """
    params = {
        "filter": "is_retracted:true",
        "per-page": PER_PAGE,
        "cursor": cursor,
        "select": FIELDS,
        "mailto": MAILTO,
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(OPENALEX_WORKS_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            wait = RETRY_BACKOFF_SECONDS ** attempt
            logger.warning(
                "Request failed (attempt %d/%d) for cursor=%s: %s. Retrying in %ds...",
                attempt, MAX_RETRIES, cursor, exc, wait,
            )
            time.sleep(wait)

    logger.error("Giving up on cursor=%s after %d attempts: %s", cursor, MAX_RETRIES, last_error)
    raise RuntimeError(f"Failed to fetch page for cursor={cursor}") from last_error


def iter_retracted_works(session: requests.Session) -> Iterator[dict[str, Any]]:
    """Yield raw OpenAlex work records for every retracted work, page by page."""
    cursor = "*"
    page_num = 1

    while cursor:
        logger.info("Fetching page %d (cursor=%s)", page_num, cursor)
        try:
            payload = fetch_page(cursor, session)
        except RuntimeError:
            logger.error("Aborting pagination at page %d due to repeated failures.", page_num)
            break

        results = payload.get("results", [])
        logger.info("Page %d returned %d works.", page_num, len(results))
        for work in results:
            yield work

        cursor = payload.get("meta", {}).get("next_cursor")
        page_num += 1

        if not results:
            break


def extract_fields(work: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields of interest from a raw OpenAlex work record."""
    primary_topic = work.get("primary_topic") or {}
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}

    # The OpenAlex API removed the legacy `host_venue` field in favor of
    # `primary_location.source`; we still surface it under the `host_venue`
    # key in our output for readability/backward compatibility.
    publisher = source.get("display_name")

    return {
        "doi": work.get("doi"),
        "title": work.get("title"),
        "primary_topic": primary_topic.get("display_name"),
        "host_venue": publisher,
        "publication_year": work.get("publication_year"),
    }


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    session = requests.Session()
    session.headers.update({"User-Agent": f"retract-radar/1.0 (mailto:{MAILTO})"})

    try:
        for work in iter_retracted_works(session):
            try:
                records.append(extract_fields(work))
            except Exception:
                logger.exception("Failed to extract fields for work id=%s", work.get("id"))
    except Exception:
        logger.exception("Unrecoverable error while fetching retracted works.")
    finally:
        session.close()

    logger.info("Collected %d retracted works. Writing to %s", len(records), OUTPUT_PATH)

    try:
        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            # Compact separators (no spaces) minimize file size.
            json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
    except OSError:
        logger.exception("Failed to write output file %s", OUTPUT_PATH)
        return 1

    logger.info("Done. Wrote %d records to %s", len(records), OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
