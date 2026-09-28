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
    for table, name in (("seatgeek", "seatgeek_snapshots.csv"), ("ticketmaster", "ticketmaster_snapshots.csv")):
        print(f"{table}: {load(conn, table, DATA / name)} rows")

    # Convenience view: one row per game per hour with hours-to-game precomputed.
    conn.execute("DROP VIEW IF EXISTS resale")
    conn.execute("""
        CREATE VIEW resale AS
        SELECT *,
               (julianday(datetime_local) - julianday(captured_at)) * 24 AS hours_to_game
        FROM seatgeek
        WHERE lowest_price IS NOT NULL
    """)
    conn.commit()
    conn.close()
    print(f"built {DB}")
