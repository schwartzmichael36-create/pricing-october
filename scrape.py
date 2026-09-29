"""
Hourly snapshot of ticket-market data for every MLB postseason game,
plus a background daily-ish log of Giants and Jets home games at MetLife.

Two sources, appended to two CSVs:
  data/seatgeek_snapshots.csv     resale market (lowest / average / highest / listing_count)
  data/ticketmaster_snapshots.csv primary market (priceRanges min / max)

Keys come from environment variables (never committed):
  SEATGEEK_CLIENT_ID   from https://seatgeek.com/account/develop
  TM_API_KEY           from https://developer.ticketmaster.com

Run:  python scrape.py
"""

import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

def load_dotenv(path: Path) -> None:
    """Local runs: read KEY=value lines from .env into the environment (GitHub Actions uses secrets)."""
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


load_dotenv(ROOT / ".env")
SG_KEY = os.environ.get("SEATGEEK_CLIENT_ID", "").strip()
TM_KEY = os.environ.get("TM_API_KEY", "").strip()

NOW = datetime.now(timezone.utc)
CAPTURED_AT = NOW.isoformat(timespec="seconds")

# Postseason window: Wild Card (Sep 29) through a Game 7 of the World Series (early Nov).
MLB_START = "2026-09-28"
MLB_END = "2026-11-08"
# NFL background log runs through the end of the regular season.
NFL_START = NOW.strftime("%Y-%m-%d")
NFL_END = "2027-01-12"

# SeatGeek titles postseason games like "ALDS: Yankees vs Red Sox - Home Game 1 (Series Game 1 - If Necessary)".
POSTSEASON_RE = re.compile(
    r"wild card|alds|nlds|alcs|nlcs|world series|postseason|home game|series game",
    re.IGNORECASE,
)


def append_rows(path: Path, rows: list[dict]) -> None:
    """Append-only, schema-safe. If the columns changed since the file was created, the rows go
    to a sibling file (name.v2.csv, name.v3.csv …) with the new header instead of misaligning
    the old one. build_db.py unions every version."""
    if not rows:
        return
    cols = list(rows[0].keys())
    if path.exists():
        with path.open(newline="") as f:
            header = next(csv.reader(f), [])
        if header != cols:
            stem, n = path.name.removesuffix(".csv").split(".v")[0], 2
            while True:
                nxt = path.with_name(f"{stem}.v{n}.csv")
                if not nxt.exists() or next(csv.reader(nxt.open(newline="")), []) == cols:
                    return append_rows(nxt, rows)
                n += 1
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new_file:
            w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- SeatGeek (resale)

def seatgeek_events(params: dict) -> list[dict]:
    """Page through /2/events and return every event."""
    out, page = [], 1
    while True:
        r = requests.get(
            "https://api.seatgeek.com/2/events",
            params={**params, "client_id": SG_KEY, "per_page": 100, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("events", []))
        meta = body.get("meta", {})
        if page * meta.get("per_page", 100) >= meta.get("total", 0):
            return out
        page += 1


def seatgeek_row(ev: dict, bucket: str) -> dict:
    stats = ev.get("stats") or {}
    home = next((p for p in ev.get("performers", []) if p.get("home_team")), {})
    away = next((p for p in ev.get("performers", []) if p.get("away_team")), {})
    venue = ev.get("venue") or {}
    return {
        "captured_at": CAPTURED_AT,
        "bucket": bucket,                       # mlb_postseason | nfl_metlife
        "event_id": ev.get("id"),
        "title": ev.get("title"),
        "datetime_local": ev.get("datetime_local"),
        "datetime_utc": ev.get("datetime_utc"),      # the one to compute hours-to-game from
        "time_tbd": ev.get("time_tbd"),
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "venue": venue.get("name"),
        "city": venue.get("city"),
        "listing_count": stats.get("listing_count"),
        "lowest_price": stats.get("lowest_price"),
        "average_price": stats.get("average_price"),
        "median_price": stats.get("median_price"),
        "highest_price": stats.get("highest_price"),
        "announce_date": ev.get("announce_date"),
        "visible_until_utc": ev.get("visible_until_utc"),
        "url": ev.get("url"),
    }


def scrape_seatgeek() -> int:
    rows = []
    mlb = seatgeek_events({
        "taxonomies.name": "mlb",
        "datetime_local.gte": MLB_START,
        "datetime_local.lte": MLB_END,
    })
    rows += [seatgeek_row(e, "mlb_postseason") for e in mlb if POSTSEASON_RE.search(e.get("title") or "")]

    for slug in ("new-york-giants", "new-york-jets"):
        nfl = seatgeek_events({
            "performers[home_team].slug": slug,
            "datetime_local.gte": NFL_START,
            "datetime_local.lte": NFL_END,
        })
        rows += [seatgeek_row(e, "nfl_metlife") for e in nfl]

    append_rows(DATA / "seatgeek_snapshots.csv", rows)
    return len(rows)


# ---------------------------------------------------------------- Ticketmaster (primary)

def tm_events(params: dict) -> list[dict]:
    out, page = [], 0
    while True:
        r = requests.get(
            "https://app.ticketmaster.com/discovery/v2/events.json",
            params={**params, "apikey": TM_KEY, "size": 200, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("_embedded", {}).get("events", []))
        pg = body.get("page", {})
        if page + 1 >= pg.get("totalPages", 0) or page >= 4:   # TM caps deep paging
            return out
        page += 1


def tm_row(ev: dict, bucket: str) -> dict:
    pr = (ev.get("priceRanges") or [{}])[0]
    venue = (ev.get("_embedded", {}).get("venues") or [{}])[0]
    start = ev.get("dates", {}).get("start", {})
    status = ev.get("dates", {}).get("status", {})
    public = (ev.get("sales") or {}).get("public") or {}
    return {
        "captured_at": CAPTURED_AT,
        "bucket": bucket,
        "event_id": ev.get("id"),
        "name": ev.get("name"),
        "local_date": start.get("localDate"),
        "local_time": start.get("localTime"),
        "time_tbd": start.get("timeTBA"),
        "status": status.get("code"),           # onsale | offsale | cancelled | postponed
        "venue": venue.get("name"),
        "city": (venue.get("city") or {}).get("name"),
        "price_type": pr.get("type"),           # standard | standard including fees
        "min_price": pr.get("min"),
        "max_price": pr.get("max"),
        "currency": pr.get("currency"),
        "sale_start": public.get("startDateTime"),
        "sale_end": public.get("endDateTime"),
        "ticket_limit": (ev.get("ticketLimit") or {}).get("info"),
        "url": ev.get("url"),
    }


def scrape_ticketmaster() -> int:
    rows = []
    mlb = tm_events({
        "classificationName": "baseball",
        "countryCode": "US",
        "startDateTime": f"{MLB_START}T00:00:00Z",
        "endDateTime": f"{MLB_END}T23:59:59Z",
    })
    rows += [tm_row(e, "mlb_postseason") for e in mlb if POSTSEASON_RE.search(e.get("name") or "")]

    for kw in ("New York Giants", "New York Jets"):
        nfl = tm_events({
            "keyword": kw,
            "classificationName": "football",
            "countryCode": "US",
            "startDateTime": f"{NFL_START}T00:00:00Z",
            "endDateTime": f"{NFL_END}T23:59:59Z",
        })
        rows += [tm_row(e, "nfl_metlife") for e in nfl if "MetLife" in ((e.get("_embedded", {}).get("venues") or [{}])[0].get("name") or "")]

    append_rows(DATA / "ticketmaster_snapshots.csv", rows)
    return len(rows)


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    missing = [k for k, v in (("SEATGEEK_CLIENT_ID", SG_KEY), ("TM_API_KEY", TM_KEY)) if not v]
    if missing:
        sys.exit(f"missing env vars: {', '.join(missing)}")

    ok = True
    for name, fn in (("seatgeek", scrape_seatgeek), ("ticketmaster", scrape_ticketmaster)):
        try:
            print(f"{CAPTURED_AT}  {name}: {fn()} rows")
        except Exception as e:                    # one source failing must not kill the other
            ok = False
            print(f"{CAPTURED_AT}  {name}: FAILED  {e!r}", file=sys.stderr)
    sys.exit(0 if ok else 1)
