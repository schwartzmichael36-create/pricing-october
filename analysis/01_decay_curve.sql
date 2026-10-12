-- Q1 · The decay curve
-- Question: how does the get-in price (cheapest listing) move as first pitch approaches,
--           and does the shape differ by round?
--
-- New idea here: CASE builds a column from rules. The first CASE turns a number of hours into
-- a bucket label; the second is just so the buckets sort in time order instead of alphabetically.
-- We take the MEDIAN of get-in prices across games in each bucket. SQLite has no MEDIAN(), so
-- we use AVG for the first pass and note it; the memo numbers come from Python where median is easy.

SELECT round,
       CASE WHEN hours_to_game > 48 THEN '48h+'
            WHEN hours_to_game > 24 THEN '24-48h'
            WHEN hours_to_game > 12 THEN '12-24h'
            WHEN hours_to_game >  6 THEN '6-12h'
            WHEN hours_to_game >  3 THEN '3-6h'
            WHEN hours_to_game >  1 THEN '1-3h'
            ELSE '0-1h' END                               AS hours_bucket,   -- not `bucket`: that's a column of the view
       COUNT(DISTINCT event_id)                           AS games,
       COUNT(*)                                           AS captures,
       ROUND(AVG(get_in_price))                           AS avg_get_in,
       ROUND(AVG(median_price))                           AS avg_median,
       ROUND(AVG(listing_count))                          AS avg_listings
FROM   resale
WHERE  bucket = 'mlb_postseason'
  AND  hours_to_game BETWEEN 0 AND 72
  AND  opponent_tbd = 0                                   -- real matchups only
GROUP  BY round, hours_bucket
ORDER  BY round,
          CASE hours_bucket WHEN '48h+' THEN 0 WHEN '24-48h' THEN 1 WHEN '12-24h' THEN 2
                      WHEN '6-12h' THEN 3 WHEN '3-6h' THEN 4 WHEN '1-3h' THEN 5 ELSE 6 END;

-- ANSWER (2026-10-12): Wild Card get-in $72 at 24–48h → $45 at 3–6h → $29 in the final hour;
-- median $185 → $59. Division Series get-in $132 → $106, median $291 → $200, listings 1,170 → 382.
-- Same shape every round: prices drift DOWN into first pitch (sellers cut to clear) and supply
-- thins; the last hour is the cheapest hour. Each round sits higher than the one before.
-- Gotcha learned here: the view already has a column called `bucket`, so an alias with the same
-- name silently grouped by the wrong thing. Aliases must not shadow columns.