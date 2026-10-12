-- Q3 · The "if necessary" question
-- Question: how is a game that might not be played priced, compared with a guaranteed game in
--           the same series at the same hours-to-game? And what happens to it after it is
--           confirmed (or cancelled)?
--
-- New idea here: a CTE (WITH … AS). A CTE is a named temporary result you can refer to like a
-- table. `g` restricts to the rows we care about and bins hours into 12-hour bands; `g1` is the
-- guaranteed-game baseline (Game 1 of the same series, same band). Then we join the two.
--
-- Note: "if necessary" here means Game 3 of a Wild Card series or Game 4/5 of a Division Series,
-- captured BEFORE the game was confirmed. Confirmation changes the title on SeatGeek, so a game
-- that becomes real shows up as if_necessary = 0 from then on.

WITH g AS (
    SELECT home_team, round, game_no, if_necessary, played,
           CAST(hours_to_game / 12 AS INT) * 12           AS band,     -- 0, 12, 24, 36, 48, 60
           get_in_price, median_price, listing_count
    FROM   game_results
    WHERE  bucket = 'mlb_postseason'
      AND  hours_to_game BETWEEN 0 AND 72
      AND  opponent_tbd = 0
),
g1 AS (
    SELECT home_team, round, band,
           AVG(get_in_price) AS g1_get_in, AVG(median_price) AS g1_median
    FROM   g
    WHERE  game_no = 1
    GROUP  BY home_team, round, band
)
SELECT g.round,
       g.home_team,
       g.game_no,
       CASE WHEN g.played = 0 THEN 'never played' ELSE 'played' END  AS outcome,
       g.band                                                        AS hours_band,
       COUNT(*)                                                      AS captures,
       ROUND(AVG(g.get_in_price))                                    AS get_in,
       ROUND(g1.g1_get_in)                                           AS game1_get_in,
       ROUND(100.0 * (AVG(g.get_in_price) - g1.g1_get_in) / g1.g1_get_in, 1)   AS get_in_vs_g1_pct,
       ROUND(AVG(g.median_price))                                    AS median,
       ROUND(g1.g1_median)                                           AS game1_median,
       ROUND(100.0 * (AVG(g.median_price) - g1.g1_median) / g1.g1_median, 1)   AS median_vs_g1_pct
FROM   g
JOIN   g1 ON g1.home_team = g.home_team AND g1.round = g.round AND g1.band = g.band
WHERE  (g.round = 'WC' AND g.game_no >= 3)               -- the games that might not happen:
   OR  (g.round = 'DS' AND g.game_no >= 4)               -- best-of-3 → G3, best-of-5 → G4/G5,
   OR  (g.round IN ('LCS','WS') AND g.game_no >= 5)      -- best-of-7 → G5+
GROUP  BY g.round, g.home_team, g.game_no, outcome, g.band
ORDER  BY g.round, g.home_team, g.game_no, g.band DESC;

-- ANSWER (2026-10-12): the expected "if necessary discount" vs Game 1 is NOT there. At the same
-- hours-to-game, maybe-games traded at par or ABOVE Game 1 (Yankees WC G3 median +17%, Astros +56%,
-- Padres +11%, Brewers DS G5 +27%). Stakes rise through a series, and that outweighs the risk the
-- game never happens. The discount only shows WITHIN a game, before vs after confirmation: the
-- Braves' WC G3 went from +21% vs Game 1 while uncertain to +66% the morning after it was forced
-- and +174% in the final hours. Memo framing: "uncertainty is priced as a delay, not a discount".
-- Limit: the baseline needs a Game 1 capture in the same 12-hour band, so only bands ≤36h compare.