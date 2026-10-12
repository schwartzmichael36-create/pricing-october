"""
Run every analysis/*.sql file against data/pricing.db and print the results as tables.

Run:  python build_db.py && python analysis/run_all.py            (all queries)
      python analysis/run_all.py 03                                (just the one starting with 03)

Each .sql file has the question and a plain-English explanation at the top, and the answer we
found at the bottom. The query itself is the part in between.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "pricing.db"
HERE = Path(__file__).resolve().parent

MAX_ROWS = 60


def show(cur, rows):
    cols = [d[0] for d in cur.description]
    rows = [tuple("" if v is None else v for v in r) for r in rows]
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c)) for i, c in enumerate(cols)]
    widths = [min(w, 60) for w in widths]
    line = "  ".join(str(c)[:60].ljust(w) for c, w in zip(cols, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows[:MAX_ROWS]:
        print("  ".join(str(v)[:60].ljust(w) for v, w in zip(r, widths)))
    if len(rows) > MAX_ROWS:
        print(f"… {len(rows) - MAX_ROWS} more rows")
    print(f"({len(rows)} rows)\n")


def main():
    pick = sys.argv[1] if len(sys.argv) > 1 else ""
    conn = sqlite3.connect(DB)
    for sql_file in sorted(HERE.glob("*.sql")):
        if pick and not sql_file.name.startswith(pick):
            continue
        text = sql_file.read_text()
        question = next((l.strip("- ").strip() for l in text.splitlines() if l.startswith("-- Q")), sql_file.name)
        print("=" * 100)
        print(f"{sql_file.name}  ·  {question}")
        print("=" * 100)
        # strip comment lines so only the statement runs
        statement = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("--"))
        cur = conn.execute(statement)
        show(cur, cur.fetchall())


if __name__ == "__main__":
    main()
