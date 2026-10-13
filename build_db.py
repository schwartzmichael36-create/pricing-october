"""
Load the two snapshot CSVs into data/pricing.db (SQLite) for analysis.
Re-runnable: drops and rebuilds both tables each time.

Run:  python build_db.py
Then: sqlite3 data/pricing.db
"""

import csv
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent / "data"
DB = DATA / "pricing.db"

NUMERIC = {
    "listing_count", "lowest_price", "average_price", "median_price", "highest_price",
    "min_price", "max_price",
    "ticket_count", "get_in_price", "avg_price", "quantity", "ticket_price", "fee", "total_price", "deal_score",
    "game_no", "played", "home_w_before", "home_l_before",
}


def load(conn: sqlite3.Connection, table: str, stem: str) -> int:
    """Union every version of a snapshot file (stem.csv, stem.v2.csv, …); missing columns are NULL."""
    files = sorted(DATA.glob(f"{stem}.csv")) + sorted(DATA.glob(f"{stem}.v*.csv"))
    if not files:
        print(f"{stem}: not found, skipping")
        return 0
    cols, chunks = [], []
    for fp in files:
        with fp.open(newline="") as f:
            reader = csv.DictReader(f)
            for c in reader.fieldnames or []:
                if c not in cols:
                    cols.append(c)
            chunks.append(list(reader))
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    types = ", ".join(f"{c} {'REAL' if c in NUMERIC else 'TEXT'}" for c in cols)
    conn.execute(f"CREATE TABLE {table} ({types})")
    rows = [[(r.get(c) or None) for c in cols] for chunk in chunks for r in chunk]
    conn.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' for _ in cols)})", rows)
    if "event_id" in cols:
        conn.execute(f"CREATE INDEX idx_{table}_event ON {table}(event_id, captured_at)")
    return len(rows)


if __name__ == "__main__":
    conn = sqlite3.connect(DB)
    for table, stem in (("seatgeek", "seatgeek_snapshots"), ("ticketmaster", "ticketmaster_snapshots"),
                        ("captures", "captures"), ("listings", "listings"),
                        ("results", "results")):          # hand-kept: one row per game
        print(f"{table}: {load(conn, table, stem)} rows")

    # Convenience view: one row per game per capture with hours-to-game precomputed.
    # `resale` now reads from the tickets.dev captures (SeatGeek's own stats went empty in 2025).
    conn.execute("DROP VIEW IF EXISTS resale")
    if conn.execute("SELECT name FROM sqlite_master WHERE name='captures'").fetchone():
        # Start times: SeatGeek's datetime_utc (snapshots before 2026-09-29 lack it, so take the
        # latest known value per event). datetime_local is venue-local and must not be compared
        # with captured_at (UTC).
        conn.execute("""
            CREATE VIEW resale AS
            WITH start AS (
                SELECT event_id, MAX(datetime_utc) AS datetime_utc
                FROM seatgeek WHERE datetime_utc IS NOT NULL AND datetime_utc <> ''
                GROUP BY event_id
            )
            SELECT c.*,
                   c.get_in_price AS lowest_price,
                   s.datetime_utc AS start_utc,
                   (julianday(s.datetime_utc) - julianday(c.captured_at)) * 24 AS hours_to_game,
                   -- parsed from the SeatGeek title so queries don't have to
                   CASE WHEN c.title LIKE '%Wild Card%'    THEN 'WC'
                        WHEN c.title LIKE '%World Series%' THEN 'WS'
                        WHEN c.title LIKE '%LCS%'          THEN 'LCS'
                        WHEN c.title LIKE '%DS%'           THEN 'DS' END AS round,
                   CAST(substr(c.title, instr(c.title, '(Game ') + 6, 1) AS INT) AS game_no,
                   CASE WHEN c.title LIKE '%If Necessary%' THEN 1 ELSE 0 END AS if_necessary,
                   CASE WHEN c.title LIKE 'TBD at %' THEN 1 ELSE 0 END AS opponent_tbd
            FROM captures c
            LEFT JOIN start s USING (event_id)
            WHERE c.ok = '1' AND c.get_in_price IS NOT NULL AND c.listing_count > 0   -- empty reads are not data
        """)
    # Team codes used in results.csv's winner column.
    conn.execute("DROP TABLE IF EXISTS teams")
    conn.execute("CREATE TABLE teams (code TEXT PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO teams VALUES (?, ?)", [
        ("NYY", "New York Yankees"), ("BOS", "Boston Red Sox"), ("HOU", "Houston Astros"),
        ("CWS", "Chicago White Sox"), ("ATL", "Atlanta Braves"), ("PHI", "Philadelphia Phillies"),
        ("SD", "San Diego Padres"), ("CHC", "Chicago Cubs"), ("TB", "Tampa Bay Rays"),
        ("CLE", "Cleveland Guardians"), ("MIL", "Milwaukee Brewers"), ("LAD", "Los Angeles Dodgers"),
    ])

    # One row per game with its result: resale joined to the hand-kept results table.
    # Join on home team + round + game number (dates are unreliable: an 8 pm ET game is the next day in UTC).
    conn.execute("DROP VIEW IF EXISTS game_results")
    conn.execute("""
        CREATE VIEW game_results AS
        SELECT r.*, x.series, x.played, x.home_w_before, x.home_l_before, x.winner, x.note,
               CASE WHEN x.winner IS NULL OR x.winner = '' THEN NULL
                    WHEN t.name = x.home THEN 1 ELSE 0 END AS home_won
        FROM resale r
        LEFT JOIN results x
          ON x.home = r.home_team
         AND x.game_no = r.game_no
         AND ((r.round = 'WC'  AND x.series LIKE '%WC%')
           OR (r.round = 'DS'  AND x.series LIKE '%DS%')
           OR (r.round = 'LCS' AND x.series LIKE '%LCS%')
           OR (r.round = 'WS'  AND x.series = 'WS'))
        LEFT JOIN teams t ON t.code = x.winner
    """)
    conn.commit()
    conn.close()
    print(f"built {DB}")
