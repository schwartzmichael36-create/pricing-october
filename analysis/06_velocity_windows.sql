-- Q6 · Sell-through velocity (window functions)
-- Question: how fast are listings disappearing for each game between captures, and does the
--           price rise when they disappear fast?
--
-- New idea here: WINDOW FUNCTIONS. `LAG(x) OVER (PARTITION BY event_id ORDER BY captured_at)`
-- means "the value of x in the PREVIOUS row for the same game, in time order". That lets one
-- row see its neighbour without a self-join. `RANK() OVER (...)` numbers rows within a group.
-- These are the Oct 26–28 lessons in the plan; the query is here so the first time you meet
-- them is on your own data.

WITH w AS (
    SELECT title, home_team, round, game_no, captured_at, hours_to_game, listing_count, median_price, get_in_price,
           LAG(listing_count) OVER (PARTITION BY event_id ORDER BY captured_at) AS prev_listings,
           LAG(median_price)  OVER (PARTITION BY event_id ORDER BY captured_at) AS prev_median,
           LAG(hours_to_game) OVER (PARTITION BY event_id ORDER BY captured_at) AS prev_hours
    FROM   resale
    WHERE  bucket = 'mlb_postseason' AND opponent_tbd = 0 AND hours_to_game BETWEEN 0 AND 72
)
SELECT round, home_team, game_no,
       ROUND(prev_hours)                                              AS from_hours,
       ROUND(hours_to_game)                                           AS to_hours,
       prev_listings                                                  AS listings_before,
       listing_count                                                  AS listings_after,
       ROUND(100.0 * (listing_count - prev_listings) / prev_listings, 1)   AS listings_chg_pct,
       ROUND(100.0 * (median_price - prev_median) / prev_median, 1)        AS median_chg_pct,
       RANK() OVER (ORDER BY (listing_count - prev_listings) / (prev_hours - hours_to_game)) AS fastest_drop_rank
FROM   w
WHERE  prev_listings IS NOT NULL AND prev_hours - hours_to_game >= 2   -- skip back-to-back captures
ORDER  BY fastest_drop_rank
LIMIT  25;

-- ANSWER (2026-10-12): the 25 fastest listing drops all happen inside the final 6 hours (e.g. Yankees
-- DS G3: 674 → 241 listings in the last 2 hours). In 22 of 25 the median FELL at the same time
-- (typically −5% to −20%). Listings vanish because sellers cut and clear (or pull), not because
-- buyers bid up. Listing count is a supply signal; say so in the memo instead of 'sell-through'.