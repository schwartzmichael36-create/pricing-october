# Postseason pricing tracker

Hourly snapshots of the resale and primary ticket markets for every 2026 MLB postseason game, with the Giants' and Jets' MetLife home games logged in the background.

**Question:** how does the postseason ticket market price uncertainty: games that may never be played, series that can end early, and matchups that change overnight?

## Data

| Source | What it gives | Table |
|---|---|---|
| SeatGeek Platform API | resale listings per game: lowest / average / median / highest price, listing count | `seatgeek` |
| Ticketmaster Discovery API | primary price range per game, on-sale status | `ticketmaster` |

One row per game per hour, from the Wild Card round (Sep 29) through the World Series.

## Run it yourself

```bash
cp .env.example .env        # add your two free API keys
pip install requests
set -a; source .env; set +a
python scrape.py            # appends one snapshot to data/*.csv
python build_db.py          # rebuilds data/pricing.db
```

The GitHub Actions workflow in `.github/workflows/scrape.yml` runs the same script every hour and commits the CSVs.

## Status

Collecting. Analysis, dashboard and memo to follow.
