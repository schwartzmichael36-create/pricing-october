# Pricing October

Hourly ticket-price tracker for the 2026 MLB postseason. Michael Schwartz's hero portfolio project for Summer 2027 sports business-analytics internships (Mets, Yankees, MLB league office, and the rest of his target list).

**The full plan is `docs/Pricing-October-Blueprint.pdf`** (15 pages; source in `docs/blueprint-source.html`). Read page 2 (what Michael must do) and page 14 (day by day) before doing anything. Follow it; don't re-plan.

## Layout
- `scrape.py` — hourly collector: SeatGeek /2/events (resale stats) + Ticketmaster Discovery v2 (primary priceRanges), appends to `data/*.csv`. Also logs Giants/Jets home games (`bucket = nfl_metlife`) for the December extension.
- `build_db.py` — rebuilds `data/pricing.db` (SQLite) from the CSVs; adds the `resale` view with `hours_to_game`.
- `.github/workflows/scrape.yml` — cron `7 * * * *`, commits new rows. Secrets: `SEATGEEK_CLIENT_ID`, `TM_API_KEY`.
- `data/results.csv` — hand-kept dimension: one row per game (series, game_no, date, home, away, played, home_w_before, home_l_before, winner, note). Michael fills it from the bracket after each game.
- `analysis/` — saved SQL (Q0–Q7 per blueprint p. 9) and `model.ipynb`. `dashboard/`, `memo/` — outputs.

## Rules
- Keys live only in `.env` (git-ignored) and GitHub Actions secrets. Never print or commit them. Never paste them into chat.
- Never create accounts for Michael (SeatGeek, Ticketmaster, GitHub, Tableau). He does those.
- Data files are append-only. Never rewrite or dedupe `data/*.csv` in place; fix in `build_db.py` instead.
- Analysis language: median not mean; listings ≠ sales; say limits first. Talk revenue and inventory, not baseball.
- Michael is learning SQL on this schedule: basics now → CTEs by Oct 21 → window functions by Oct 28. Write queries he can read and modify, and explain them; don't hand him black boxes.
- Publish date is Nov 2 (LinkedIn + resume + TeamWork Online). Outreach Nov 3–5.

## Status
See memory (`MEMORY.md` in this project's Claude memory dir) for what's live and what's blocked.
