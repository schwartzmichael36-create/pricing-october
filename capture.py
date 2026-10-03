"""
Resale listing captures via tickets.dev, on a credit budget.

Runs every hour after scrape.py. Reads the latest SeatGeek snapshot to find the
games currently listed and captures each one as it crosses a fixed point before
first pitch, so every game ends up with the same price curve:

  MLB postseason   72 h, 48 h, 24 h, 12 h, 6 h, 3 h, 1 h   (7 captures per game)
  NFL (Giants/Jets) 72 h, 24 h, 3 h                          (December extension)

A game is due when it has crossed a milestone and hasn't been captured since
crossing it. Closest first pitch goes first; New York games win ties.

Why milestones: spending "N per day, evenly" burned each UTC day's credits
overnight (the UTC day starts at 8 pm ET) and left nothing for the final hours
before first pitch, which is where prices move.

Guards (all three must allow a capture):
  DAILY_CAP    captures per UTC day
  CYCLE_CAP    captures per tickets.dev billing cycle (1,000 credits, renews on the 28th)
  40 minutes   wall-clock per run, so a run never overlaps the next one

Outputs (append-only, versioned if the columns change):
  data/captures*.csv   one row per capture: stats (get-in, median, count …)
  data/listings*.csv   one row per listing per capture (section, row, price …)

Key: TICKETSDEV_API_KEY (.env locally, GitHub secret in Actions).
Run:  python capture.py            (live)
      python capture.py --dry-run  (print the plan, spend nothing)
"""

import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from scrape import DATA, ROOT, append_rows, load_dotenv

load_dotenv(ROOT / ".env")
KEY = os.environ.get("TICKETSDEV_API_KEY", "").strip()
DRY = "--dry-run" in sys.argv

NOW = datetime.now(timezone.utc)
CAPTURED_AT = NOW.isoformat(timespec="seconds")

MLB_MILESTONES = (72, 48, 24, 12, 6, 3, 1)      # hours before first pitch
NFL_MILESTONES = (72, 24, 3)

DAILY_CAP = 40                                   # safety net, not the pacing mechanism
CYCLE_CAP = 970                                  # of 1,000 credits per billing cycle
CYCLE_DAY = 28                                   # plan bought Sep 28; renews on the 28th

CAP_CSV = DATA / "captures.csv"
LIST_CSV = DATA / "listings.csv"


def parse_iso(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def cycle_start() -> str:
    """ISO date the current billing cycle began (the most recent 28th)."""
    y, m = NOW.year, NOW.month
    if NOW.day < CYCLE_DAY:
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return f"{y:04d}-{m:02d}-{CYCLE_DAY:02d}"


def latest_snapshot() -> list[dict]:
    """Rows from the most recent scrape.py run (one per listed game), across every file version."""
    files = sorted(DATA.glob("seatgeek_snapshots.csv")) + sorted(DATA.glob("seatgeek_snapshots.v*.csv"))
    rows = [r for fp in files for r in csv.DictReader(fp.open())]
    if not rows:
        return []
    last = max(r["captured_at"] for r in rows)
    return [r for r in rows if r["captured_at"] == last and r.get("url")]


def capture_files() -> list[Path]:
    """Every version of the captures log (captures.csv, captures.v2.csv, …).
    Reading only the first one is how 390 credits got spent on 2026-09-30."""
    return sorted(DATA.glob("captures.csv")) + sorted(DATA.glob("captures.v*.csv"))


def capture_history() -> tuple[dict, int, int]:
    """Last capture time per event; captures today (UTC); captures this billing cycle."""
    last, today, cycle = {}, 0, 0
    since = cycle_start()
    for fp in capture_files():
        for r in csv.DictReader(fp.open()):
            if r.get("ok") != "1":
                continue
            last[r["event_id"]] = max(last.get(r["event_id"], ""), r["captured_at"])
            today += r["captured_at"][:10] == CAPTURED_AT[:10]
            cycle += r["captured_at"][:10] >= since
    return last, today, cycle


def start_time(row: dict) -> datetime:
    return parse_iso(row.get("datetime_utc") or row["datetime_local"])   # old snapshots lack datetime_utc


def due(row: dict, last_iso) -> bool:
    """Has this game crossed a milestone it hasn't been captured at yet?"""
    start = start_time(row)
    h_to_game = (start - NOW).total_seconds() / 3600
    if h_to_game < -0.5:                                  # under way or over
        return False
    marks = NFL_MILESTONES if row["bucket"] == "nfl_metlife" else MLB_MILESTONES
    crossed = [m for m in marks if h_to_game <= m]
    if not crossed:                                       # more than 72 h out
        return False
    if not last_iso:
        return True
    h_at_last = (start - parse_iso(last_iso)).total_seconds() / 3600
    return h_at_last > min(crossed)                       # last look was before the newest milestone


def plan() -> tuple[list[dict], int, int]:
    last, today, cycle = capture_history()
    cands = [r for r in latest_snapshot() if due(r, last.get(r["event_id"]))]
    cands.sort(key=lambda r: (start_time(r), "New York" not in (r.get("home_team") or "")))
    room = max(0, min(DAILY_CAP - today, CYCLE_CAP - cycle))
    return cands[:room], today, cycle


def do_capture(row: dict) -> tuple[dict, list[dict]]:
    r = requests.get(
        "https://api.tickets.dev/v1/capture",
        params={"url": row["url"]},
        headers={"x-api-key": KEY},
        timeout=90,
    )
    base = {
        "captured_at": CAPTURED_AT,
        "bucket": row["bucket"],
        "event_id": row["event_id"],
        "title": row["title"],
        "datetime_local": row["datetime_local"],
        "datetime_utc": row.get("datetime_utc"),
        "home_team": row.get("home_team"),
        "away_team": row.get("away_team"),
        "source": "seatgeek",
        "http": r.status_code,
        "ok": "0",
    }
    if r.status_code != 200:
        return {**base, "error": r.text[:200].replace("\n", " "), "listing_count": None, "ticket_count": None,
                "get_in_price": None, "median_price": None, "avg_price": None, "max_price": None}, []
    body = r.json()
    st = body.get("stats") or {}
    cap = {**base, "ok": "1", "error": "",
           "listing_count": st.get("listingCount"), "ticket_count": st.get("ticketCount"),
           "get_in_price": st.get("getInPrice"), "median_price": st.get("medianPrice"),
           "avg_price": st.get("avgPrice"), "max_price": st.get("maxPrice")}
    listings = [{
        "captured_at": CAPTURED_AT, "event_id": row["event_id"], "listing_id": l.get("listingId"),
        "inventory_type": l.get("inventoryType"), "section": l.get("section"), "row": l.get("row"),
        "quantity": l.get("quantity"), "ticket_price": l.get("ticketPrice"), "fee": l.get("fee"),
        "total_price": l.get("totalPrice"), "deal_score": l.get("dealScore"),
    } for l in body.get("listings") or []]
    return cap, listings


if __name__ == "__main__":
    todo, spent, cycle = plan()
    print(f"{CAPTURED_AT}  due: {len(todo)}  today: {spent}/{DAILY_CAP}  cycle since {cycle_start()}: {cycle}/{CYCLE_CAP}")
    for r in todo:
        h = (start_time(r) - NOW).total_seconds() / 3600
        print(f"   {h:5.1f} h  {r['title'][:70]}")
    if DRY:
        sys.exit(0)
    if not KEY:
        sys.exit("missing env var: TICKETSDEV_API_KEY")
    caps, lists, failed = [], [], 0
    for r in todo:
        if (datetime.now(timezone.utc) - NOW).total_seconds() > 40 * 60:   # stay inside the hourly slot
            print("   time budget reached; remaining games roll to the next run")
            break
        cap, ls = do_capture(r)
        caps.append(cap); lists += ls
        failed += cap["ok"] != "1"
        if cap["ok"] != "1":
            print(f"   FAILED {r['title'][:50]}: {cap['http']} {cap['error'][:120]}", file=sys.stderr)
    append_rows(CAP_CSV, caps)
    append_rows(LIST_CSV, lists)
    print(f"   captured {len(caps) - failed}, failed {failed}, listings {len(lists)}")
