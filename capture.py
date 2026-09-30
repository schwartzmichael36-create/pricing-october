"""
Resale listing captures via tickets.dev, on a credit budget.

Runs every hour after scrape.py. Reads the latest SeatGeek snapshot to find the
games currently listed, decides which ones are "due" for a capture based on how
close they are to first pitch, and captures them in priority order until the
daily cap is hit.

Cadence (per game):
  <= 12 h to first pitch   every 3 h
  <= 48 h                  every 6 h
  <= 7 days                once a day
  further out              every 3 days
NFL (Giants/Jets) games:   once a day, only inside 14 days of kickoff

Budget: DAILY_CAP captures per UTC day (1,000 credits / ~34 days ≈ 29/day),
paced across runs in proportion to the time since the last run.

Outputs (append-only):
  data/captures.csv   one row per capture: stats (get-in, median, count …)
  data/listings.csv   one row per listing per capture (section, row, price …)

Key: TICKETSDEV_API_KEY (.env locally, GitHub secret in Actions).
Run:  python capture.py            (live)
      python capture.py --dry-run  (print the plan, spend nothing)
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from scrape import DATA, ROOT, append_rows, load_dotenv

import os

load_dotenv(ROOT / ".env")
KEY = os.environ.get("TICKETSDEV_API_KEY", "").strip()
DRY = "--dry-run" in sys.argv

NOW = datetime.now(timezone.utc)
# Wild Card round (Sep 29 – Oct 1): 12 games in three days, so a bigger day. 32 after that.
# Unused credits roll over, and the DS/LCS/WS days have far fewer games listed.
# Budget after the 2026-09-30 overspend (≈466 of 1,000 used): 30 for the last Wild Card day,
# then 18/day through the plan's Oct 28 renewal, when 1,000 fresh credits arrive for the WS.
_day = NOW.strftime("%Y-%m-%d")
DAILY_CAP = 30 if _day <= "2026-10-01" else (18 if _day < "2026-10-28" else 32)
CAPTURED_AT = NOW.isoformat(timespec="seconds")

CAP_CSV = DATA / "captures.csv"
LIST_CSV = DATA / "listings.csv"


def parse_iso(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


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


def capture_history() -> tuple[dict, int]:
    """Last capture time per event, and how many captures already happened today (UTC)."""
    last, today = {}, 0
    for fp in capture_files():
        for r in csv.DictReader(fp.open()):
            if r.get("ok") != "1":
                continue
            last[r["event_id"]] = max(last.get(r["event_id"], ""), r["captured_at"])
            if r["captured_at"][:10] == CAPTURED_AT[:10]:
                today += 1
    return last, today


def hours_since(last_iso) -> float:
    return 1e9 if not last_iso else (NOW - parse_iso(last_iso)).total_seconds() / 3600


def due(row: dict, last_iso) -> bool:
    start = row.get("datetime_utc") or row["datetime_local"]   # older snapshots lack datetime_utc
    h_to_game = (parse_iso(start) - NOW).total_seconds() / 3600
    if h_to_game < -4:                       # game is over
        return False
    since = hours_since(last_iso)
    if row["bucket"] == "nfl_metlife":
        return h_to_game <= 14 * 24 and since >= 23
    if h_to_game <= 12:
        return since >= 2.75
    if h_to_game <= 48:
        return since >= 5.75
    if h_to_game <= 7 * 24:
        return since >= 23
    return since >= 71                       # placeholders a week+ out: every 3 days


def per_run_room(last: dict, today: int) -> int:
    """Pace the daily budget across runs, whatever cadence GitHub actually gives us.

    GitHub's cron is best-effort: overnight it fired every 4–6 hours instead of hourly, and a
    single run spent the whole day's 32 credits. So each run may spend only its share of the
    day, proportional to the time since the previous run (min 3, max 8 hours' worth).
    """
    newest = max(last.values(), default=None)
    gap_h = min(8.0, hours_since(newest)) if newest else 8.0
    share = max(3, round(DAILY_CAP * gap_h / 24))
    return max(0, min(share, DAILY_CAP - today))


def plan() -> list[dict]:
    last, today = capture_history()
    snap = latest_snapshot()
    cands = [r for r in snap if due(r, last.get(r["event_id"]))]
    # closest to first pitch first; New York games win ties
    cands.sort(key=lambda r: (r["datetime_local"], "New York" not in (r.get("home_team") or "")))
    return cands[:per_run_room(last, today)]


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
    todo = plan()
    _, spent = capture_history()
    print(f"{CAPTURED_AT}  due: {len(todo)}  spent today: {spent}/{DAILY_CAP}")
    for r in todo:
        print(f"   {r['datetime_local'][:16]}  {r['title'][:70]}")
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
