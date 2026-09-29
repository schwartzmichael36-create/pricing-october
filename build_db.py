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
}


def load(conn: sqlite3.Connection, table: str, csv_path: Path) -> int:
    if not csv_path.exists():
        print(f"{csv_path.name}: not found, skipping")
        return 0
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    types = ", ".join(f"{c} {'REAL' if c in NUMERIC else 'TEXT'}" for c in cols)
    conn.execute(f"CREATE TABLE {table} ({types})")
    conn.executemany(
        f"INSERT INTO {table} VALUES ({', '.join('?' for _ in cols)})",
        [[(r[c] or None) for c in cols] for r in rows],
    )
    conn.execute(f"CREATE INDEX idx_{table}_event ON {table}(event_id, captured_at)")
    return len(rows)


if __name__ == "__main__":
    conn = sqlite3.connect(DB)
    for table, name in (("seatgeek", "seatgeek_snapshots.csv"), ("ticketmaster", "ticketmaster_snapshots.csv"),
                        ("captures", "captures.csv"), ("listings", "listings.csv")):
        print(f"{table}: {load(conn, table, DATA / name)} rows")

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
                   (julianday(s.datetime_utc) - julianday(c.captured_at)) * 24 AS hours_to_game
            FROM captures c
            LEFT JOIN start s USING (event_id)
            WHERE c.ok = '1' AND c.get_in_price IS NOT NULL
        """)
    conn.commit()
    conn.close()
    print(f"built {DB}")
